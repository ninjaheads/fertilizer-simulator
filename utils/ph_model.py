import math

def predict_final_ph(
    raw_ph: float = 7.0,
    phosphate_mass_g_per_l: float = 2.0,
    ammonium_mmol_per_l: float = 0.350,
    alkalinity_meq_per_l: float = 1.0,
    alpha: float = 0.4,
    beta: float = 1.0,
    gamma: float = 0.5
) -> float:
    """
    養液中のリン酸とアンモニウムの量、および原水のアルカリ度からpHを推定する簡易モデル。

    Parameters:
    - raw_ph: 原水のpH
    - phosphate_mass_g_per_l: 添加するリン酸（H3PO4）の濃度 [g/L]
    - ammonium_mmol_per_l: アンモニウム濃度 [mmol/L]
    - alkalinity_meq_per_l: アルカリ度 [meq/L]
    - alpha: リン酸によるpH低下の経験係数
    - beta: アルカリ度によるpH維持の経験係数
    - gamma: NH4+によるpH低下の係数

    Returns:
    - 推定される養液のpH値（0未満にはならない）
    """
    h3po4_molar_mass = 98.0
    try:
        phosphate_mmol_per_l = phosphate_mass_g_per_l * 1000 / h3po4_molar_mass
        if phosphate_mmol_per_l <= 0:
            return raw_ph

        log_term = -alpha * math.log10(phosphate_mmol_per_l)  # ← 修正ポイント
        alk_term = beta * alkalinity_meq_per_l
        nh4_term = gamma * ammonium_mmol_per_l

        predicted_ph = raw_ph + log_term - alk_term - nh4_term
        return round(max(0.0, predicted_ph), 2)

    except Exception:
        return None

if __name__ == "__main__":
    # ここは「テスト時だけ」実行される！
    print(predict_final_ph())