import math

import numpy as np
import pandas as pd


def analyze_wait_times(series, service_target=None):
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    values = values[values >= 0]
    if len(values) < 3:
        raise ValueError("Se necesitan al menos tres tiempos de espera numéricos y no negativos.")

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

    target = float(service_target) if service_target not in {None, ""} else float(percentiles.loc[0.75])
    if target < 0 or not math.isfinite(target):
        raise ValueError("La meta de servicio debe ser un número no negativo.")
    within_target = float((values <= target).mean() * 100)

    if skewness > 1:
        shape = "Asimetría positiva fuerte"
        explanation = "La mayoría de las llamadas se atiende rápido, pero una cola de esperas largas eleva el promedio."
    elif skewness > 0.5:
        shape = "Asimetría positiva moderada"
        explanation = "Existen esperas largas suficientes para separar el promedio de la experiencia típica."
    elif skewness < -0.5:
        shape = "Asimetría negativa"
        explanation = "La distribución concentra casos altos y presenta una cola hacia esperas menores."
    else:
        shape = "Distribución aproximadamente simétrica"
        explanation = "Media y mediana son similares; aun así, los percentiles muestran el nivel de servicio de la cola."

    recommendations = []
    if skewness > 0.5:
        recommendations.append("Usa la mediana como indicador de experiencia típica y P90/P95 para controlar la cola.")
    if within_target < 80:
        recommendations.append("Menos del 80% cumple la meta: ajusta dotación en horas pico y revisa el enrutamiento de llamadas.")
    if extreme_count:
        recommendations.append(f"Investiga los {extreme_count} casos sobre el límite de valores extremos ({extreme_limit:.2f}).")
    recommendations.append("Segmenta los tiempos por hora, agente, categoría y canal para localizar el origen de las esperas largas.")

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
        "within_target": within_target,
        "histogram_labels": labels,
        "histogram_counts": counts.astype(int).tolist(),
        "recommendations": recommendations,
    }
