import requests
import pandas as pd
import numpy as np
import warnings
import yfinance as yf
from collections import Counter

from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, log_loss
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer

from xgboost import XGBClassifier
from hmmlearn import hmm
from fredapi import Fred

warnings.filterwarnings("ignore")

# =========================================================
# CONFIGURAÇÕES
# =========================================================
FRED_KEY = "d8e0b702562161731979cac670480abc"  # substitua pela sua chave
x = 1500  # dias de histórico

features = [
    "retorno", "volatilidade", "retorno_30d",
    "distancia_mm50", "volume_norm",
    "m2_variacao", "fed_rate", "fear_greed",
    "fear_greed_variacao", "fed_rate_variacao",
    "fear_greed_mm7", "volume_tendencia",
    "mayer_multiple", "rsi_14"
]

# =========================================================
# 1) BUSCA DE DADOS BTC (YAHOO FINANCE)
# =========================================================
def buscar_dados_btc(dias=x):
    btc = yf.download("BTC-USD", period=f"{dias}d", interval="1d", progress=False)
    btc = btc.reset_index()
    btc.columns = [c[0] if isinstance(c, tuple) else c for c in btc.columns]

    df = pd.DataFrame()
    df["data"] = pd.to_datetime(btc["Date"])
    df["data_only"] = df["data"].dt.date
    df["preco"] = btc["Close"].values
    df["volume"] = btc["Volume"].values
    df["timestamp"] = df["data"].astype(int) // 10**6

    return df[["timestamp", "data", "data_only", "preco", "volume"]].dropna().reset_index(drop=True)


# =========================================================
# 2) FEATURES TÉCNICAS
# =========================================================
def calcular_features(df):
    df = df.copy()
    df["retorno"] = df["preco"].pct_change()
    df["volatilidade"] = df["retorno"].rolling(5).std()
    df["retorno_30d"] = df["preco"].pct_change(30)
    df["media_50"] = df["preco"].rolling(50).mean()
    df["distancia_mm50"] = (df["preco"] - df["media_50"]) / df["media_50"]
    df["volume_media"] = df["volume"].rolling(20).mean()
    df["volume_norm"] = (df["volume"] - df["volume_media"]) / df["volume_media"]
    return df.dropna().reset_index(drop=True)


# =========================================================
# 3) HMM PARA DEFINIR REGIMES
# =========================================================
def treinar_hmm(df):
    df = df.copy()

    features_hmm = ["retorno", "volatilidade", "retorno_30d", "distancia_mm50", "volume_norm"]
    X = df[features_hmm].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    melhor_modelo = None
    melhor_score = -np.inf
    melhor_bic = np.inf

    seeds = [7, 21, 42, 84, 128]  # suficiente

    for seed in seeds:
        try:
            m = hmm.GaussianHMM(
                n_components=4,
                covariance_type="diag",   # 🔥 mais estável que full
                n_iter=1000,              # 🔥 suficiente
                tol=1e-4,
                min_covar=1e-4,
                random_state=seed
            )

            m.fit(X_scaled)

            logL = m.score(X_scaled)

            # 🔥 BIC (melhor critério que só log-likelihood)
            n_params = m.n_components * (m.n_components - 1) + 2 * m.n_components * X_scaled.shape[1]
            bic = -2 * logL + n_params * np.log(len(X_scaled))

            if bic < melhor_bic:
                melhor_bic = bic
                melhor_score = logL
                melhor_modelo = m

        except Exception as e:
            print(f"[HMM erro seed {seed}] {e}")

    if melhor_modelo is None:
        raise RuntimeError("Nenhum HMM convergiu")

    df["estado"] = melhor_modelo.predict(X_scaled)

    medias = df.groupby("estado")["retorno"].mean().sort_values()

    nomes = ["Bear Forte", "Bear Fraco", "Lateral", "Bull"]
    mapa = {estado: nomes[i] for i, estado in enumerate(medias.index)}

    df["regime"] = df["estado"].map(mapa)

    print(f"[HMM] Melhor BIC: {melhor_bic:.2f}")

    return df, melhor_modelo, scaler, mapa


# =========================================================
# 4) MATRIZ DE TRANSIÇÃO ENTRE REGIMES
# =========================================================
def calcular_matriz_transicao(df):
    estados = ["Bear Forte", "Bear Fraco", "Lateral", "Bull"]
    matriz = pd.DataFrame(0, index=estados, columns=estados)
    for i in range(1, len(df)):
        de = df["regime"].iloc[i - 1]
        para = df["regime"].iloc[i]
        if de in estados and para in estados:
            matriz.loc[de, para] += 1
    return matriz.div(matriz.sum(axis=1), axis=0).round(3)


# =========================================================
# 5) DADOS MACRO (FRED)
# =========================================================
def buscar_dados_macro(fred_key):
    fred = Fred(api_key=fred_key)

    m2 = fred.get_series("M2SL", observation_start="2022-01-01")
    m2.index = pd.to_datetime(m2.index)
    m2 = m2.resample("D").interpolate()

    fed_rate = fred.get_series("FEDFUNDS", observation_start="2022-01-01")
    fed_rate.index = pd.to_datetime(fed_rate.index)
    fed_rate = fed_rate.resample("D").interpolate()

    df_macro = pd.DataFrame({
        "m2": m2,
        "fed_rate": fed_rate
    }).dropna().sort_index()

    df_macro["data_only"] = df_macro.index.date
    return df_macro


# =========================================================
# 6) FEAR & GREED (ALTERNATIVE.ME)
# =========================================================
def buscar_fear_greed():
    url = f"https://api.alternative.me/fng/?limit={x}&format=json"
    resp = requests.get(url, timeout=30).json()

    fg_data = pd.DataFrame(resp["data"])
    fg_data["timestamp"] = pd.to_datetime(fg_data["timestamp"].astype(int), unit="s")
    fg_data["fear_greed"] = fg_data["value"].astype(int)
    fg_data = fg_data[["timestamp", "fear_greed"]].sort_values("timestamp")
    fg_data["data_only"] = fg_data["timestamp"].dt.date

    print(f"Fear & Greed: {len(fg_data)} dias disponíveis")
    print(f"De: {fg_data['data_only'].min()} até {fg_data['data_only'].max()}")
    return fg_data


# =========================================================
# 7) INTEGRAÇÃO BTC + MACRO + F&G
# =========================================================
def integrar_dados(df_btc, df_macro, fg_data):
    df = df_btc.copy()

    macro = df_macro[["data_only", "m2", "fed_rate"]].copy()
    fg = fg_data[["data_only", "fear_greed"]].copy()

    df_merged = df.merge(macro, on="data_only", how="left")
    df_merged = df_merged.merge(fg, on="data_only", how="left")

    df_merged["m2"] = df_merged["m2"].ffill()
    df_merged["fed_rate"] = df_merged["fed_rate"].ffill()
    df_merged["fear_greed"] = df_merged["fear_greed"].ffill()

    df_merged["m2_variacao"] = df_merged["m2"].pct_change(30) * 100

    # Mayer Multiple
    df_merged["mm200"] = df_merged["preco"].rolling(200).mean()
    df_merged["mayer_multiple"] = df_merged["preco"] / df_merged["mm200"]

    # RSI 14 dias
    delta = df_merged["preco"].diff()
    ganho = delta.clip(lower=0).rolling(14).mean()
    perda = (-delta.clip(upper=0)).rolling(14).mean()
    rs = ganho / perda
    df_merged["rsi_14"] = 100 - (100 / (1 + rs))

    df_merged = df_merged.dropna().reset_index(drop=True)
    return df_merged


# =========================================================
# 8) TREINO XGBOOST + CALIBRAÇÃO DE PROBABILIDADE
# =========================================================
def treinar_xgboost_calibrado(df, features):
    df_model = df.copy()
    df_model["regime_amanha"] = df_model["regime"].shift(-1)
    df_model = df_model.dropna(subset=["regime_amanha"]).reset_index(drop=True)

    X_df = df_model[features].copy()
    y = df_model["regime_amanha"].values

    imputer = SimpleImputer(strategy="mean")
    X = imputer.fit_transform(X_df)

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    n = len(X)
    split_train = int(n * 0.667)
    split_calib = int(n * 0.83)

    X_train = X[:split_train]
    y_train = y_enc[:split_train]
    X_calib = X[split_train:split_calib]
    y_calib = y_enc[split_train:split_calib]
    X_test = X[split_calib:]
    y_test = y_enc[split_calib:]

    # garantir todas as classes no treino
    classes_train = set(y_train)
    classes_all = set(y_enc)
    faltantes = classes_all - classes_train
    if faltantes:
        for classe in faltantes:
            idx = np.where(y_enc == classe)[0][0]
            X_train = np.vstack([X_train, X[idx]])
            y_train = np.append(y_train, y_enc[idx])

    # balanceamento de classes
    contagem = Counter(y_enc)
    total = len(y_enc)
    class_weights = {c: total / (len(contagem) * v) for c, v in contagem.items()}
    sample_weights = np.array([class_weights[y] for y in y_train])

    base_model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        objective="multi:softprob",
        num_class=len(le.classes_),
        eval_metric="mlogloss",
        random_state=42
    )
    base_model.fit(X_train, y_train, sample_weight=sample_weights)

    calibrated_model = CalibratedClassifierCV(
        estimator=base_model,
        method="sigmoid",
        cv=None
    )
    calibrated_model.fit(X_calib, y_calib)

    y_pred_test = calibrated_model.predict(X_test)
    y_proba_test = calibrated_model.predict_proba(X_test)

    acc = accuracy_score(y_test, y_pred_test)
    try:
        ll = log_loss(y_test, y_proba_test)
    except Exception:
        ll = np.nan

    feature_names = list(X_df.columns)
    importancias = pd.Series(base_model.feature_importances_, index=feature_names).sort_values(ascending=False)

    return {
        "df_model": df_model,
        "imputer": imputer,
        "X_df": X_df,
        "X": X,
        "label_encoder": le,
        "base_model": base_model,
        "calibrated_model": calibrated_model,
        "accuracy": acc,
        "log_loss": ll,
        "feature_importances": importancias,
        "X_test": X_test,
        "y_test": y_test
    }


# =========================================================
# 9) EXECUÇÃO DO PIPELINE
# =========================================================
print("Buscando dados BTC...")
df = buscar_dados_btc()

print("Calculando features...")
df = calcular_features(df)

print("Treinando HMM...")
df, modelo_hmm, scaler, mapa = treinar_hmm(df)

print("Buscando dados macro do FRED...")
df_macro = buscar_dados_macro(FRED_KEY)

print("Buscando Fear & Greed...")
fg_data = buscar_fear_greed()

print("Integrando bases...")
df_merged = integrar_dados(df, df_macro, fg_data)

# Propagando regime do HMM para df_merged
regime_map = dict(zip(df["data_only"], df["regime"]))
df_merged["regime"] = df_merged["data_only"].map(regime_map)
df_merged = df_merged.dropna(subset=["regime"]).reset_index(drop=True)

df_merged["fear_greed_variacao"] = df_merged["fear_greed"].pct_change(7) * 100
df_merged["fed_rate_variacao"] = df_merged["fed_rate"].diff(30)
df_merged["fear_greed_mm7"] = df_merged["fear_greed"].rolling(7).mean()
df_merged["volume_tendencia"] = df_merged["volume_norm"].rolling(7).mean()

df_merged = df_merged.dropna().reset_index(drop=True)

print("Treinando XGBoost calibrado...")
resultado = treinar_xgboost_calibrado(df_merged, features)

calibrated_model = resultado["calibrated_model"]
base_model = resultado["base_model"]
le = resultado["label_encoder"]
importancias = resultado["feature_importances"]

# =========================================================
# 10) RELATÓRIO
# =========================================================
regime_atual = df_merged["regime"].iloc[-1]
preco_atual = df_merged["preco"].iloc[-1]
volume_hoje = df_merged["volume_norm"].iloc[-1] * 100
distancia_mm50 = df_merged["distancia_mm50"].iloc[-1] * 100
acuracia = resultado["accuracy"]
ll = resultado["log_loss"]

print("\n" + "="*60)
print("RELATÓRIO DO SISTEMA")
print("="*60)
print(f"Preço BTC:        ${preco_atual:,.2f}")
print(f"Regime atual:     {regime_atual}")
print(f"Dist. MM50:       {distancia_mm50:.1f}%")
print(f"Volume vs média:  {volume_hoje:.1f}%")
print(f"Acurácia teste:   {acuracia*100:.1f}%")
if not np.isnan(ll):
    print(f"Log loss teste:   {ll:.4f}")

print("\n=== Importância das Features ===")
for feat, imp in importancias.items():
    print(f"  {feat}: {imp*100:.2f}%")

# =========================================================
# 11) PREVISÃO PARA AMANHÃ
# =========================================================
df_pred = df_merged.copy()
df_pred["regime_amanha"] = df_pred["regime"].shift(-1)
df_pred = df_pred.dropna(subset=["regime_amanha"]).reset_index(drop=True)

X_pred_df = df_pred[features].copy()
X_pred_df = X_pred_df.reindex(columns=resultado["X_df"].columns, fill_value=0)
X_pred = resultado["imputer"].transform(X_pred_df)

ultimo = X_pred[-1].reshape(1, -1)
pred_enc = calibrated_model.predict(ultimo)[0]
pred_regime = le.inverse_transform([pred_enc])[0]
probas = calibrated_model.predict_proba(ultimo)[0]
classes = list(le.classes_)

print("\n" + "="*60)
print("PREVISÃO PARA AMANHÃ")
print("="*60)
print(f"Regime previsto: {pred_regime}")
for classe_idx, prob in sorted(enumerate(probas), key=lambda x: -x[1]):
    print(f"  {classes[classe_idx]}: {prob*100:.1f}%")

# Matriz de transição
matriz = calcular_matriz_transicao(df_merged)
print(f"\n=== Matriz de Transição a partir de {regime_atual} ===")
for col in ["Bear Forte", "Bear Fraco", "Lateral", "Bull"]:
    if col in matriz.columns:
        prob = matriz.loc[regime_atual, col]
        if prob > 0:
            print(f"  {col}: {prob*100:.1f}%")
print("="*60)
print(f"Dias analisados: {x}")