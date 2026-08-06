import math

import numpy as np
import pandas as pd


def analyze_distribution(series, target=None, target_direction="maximum", variable_name="Variable"):
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    values = values[values >= 0]
    if len(values) < 3:
        raise ValueError("Se necesitan al menos tres valores numéricos y no negativos.")

    percentiles = values.quantile([0.5, 0.75, 0.9, 0.95, 0.99])
    mean = float(values.mean())
    median = float(percentiles.loc[0.5])
    skewness = float(values.skew()) if len(values) >= 3 else 0.0
    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))
    iqr = q3 - q1
    extreme_limit = q3 + 1.5 * iqr
    extreme_count = int((values > extreme_limit).sum())
    tail_limit = float(percentiles.loc[0.95])
    tail_count = int((values >= tail_limit).sum())

    edges = np.histogram_bin_edges(values, bins="fd")
    if len(edges) < 5:
        edges = np.linspace(float(values.min()), float(values.max()) or 1, 6)
    if len(edges) > 31:
        edges = np.linspace(float(values.min()), float(values.max()), 31)
    counts, edges = np.histogram(values, bins=edges)
    labels = [f"{edges[index]:.1f}–{edges[index + 1]:.1f}" for index in range(len(counts))]

    target = float(target) if target not in {None, ""} else float(percentiles.loc[0.75])
    if target < 0 or not math.isfinite(target):
        raise ValueError("La meta debe ser un número no negativo.")
    if target_direction not in {"maximum", "minimum"}:
        raise ValueError("El criterio de cumplimiento no es válido.")
    within_target = float(((values <= target) if target_direction == "maximum" else (values >= target)).mean() * 100)

    if skewness > 1:
        shape = "Asimetría positiva fuerte"
        explanation = f"La mayoría de los valores de {variable_name} se concentra en niveles bajos, pero una cola de casos altos eleva el promedio."
    elif skewness > 0.5:
        shape = "Asimetría positiva moderada"
        explanation = f"Existen valores altos de {variable_name} suficientes para separar el promedio del comportamiento típico."
    elif skewness < -0.5:
        shape = "Asimetría negativa"
        explanation = f"La distribución de {variable_name} concentra casos altos y presenta una cola hacia valores menores."
    else:
        shape = "Distribución aproximadamente simétrica"
        explanation = "Media y mediana son similares; aun así, los percentiles permiten observar los extremos de la distribución."

    recommendations = []
    if skewness > 0.5:
        recommendations.append("Usa la mediana como indicador del valor típico y P90/P95 para controlar la cola superior.")
    if within_target < 80:
        recommendations.append("Menos del 80% cumple la meta: segmenta la variable para identificar grupos, periodos o categorías responsables.")
    if extreme_count:
        recommendations.append(f"Investiga los {extreme_count} casos sobre el límite de valores extremos ({extreme_limit:.2f}).")
    recommendations.append("Compara la distribución por fecha y categorías disponibles para localizar el origen de los valores extremos.")

    return {
        "count": len(values),
        "invalid": int(len(series) - len(values)),
        "mean": mean,
        "median": median,
        "p75": float(percentiles.loc[0.75]),
        "p90": float(percentiles.loc[0.9]),
        "p95": tail_limit,
        "p99": float(percentiles.loc[0.99]),
        "min": float(values.min()),
        "max": float(values.max()),
        "skewness": skewness,
        "shape": shape,
        "explanation": explanation,
        "extreme_limit": extreme_limit,
        "extreme_count": extreme_count,
        "tail_count": tail_count,
        "service_target": target,
        "target_direction": target_direction,
        "within_target": within_target,
        "histogram_labels": labels,
        "histogram_counts": counts.astype(int).tolist(),
        "recommendations": recommendations,
    }


def analyze_wait_times(series, service_target=None):
    """Compatibilidad con el análisis original de tiempos de espera."""
    return analyze_distribution(series, service_target, "maximum", "tiempo de espera")
