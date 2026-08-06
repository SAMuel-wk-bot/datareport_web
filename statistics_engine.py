import math

import numpy as np
import pandas as pd


def _numbers(series):
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float).tolist()
    if not values:
        raise ValueError("La columna no contiene valores numéricos válidos.")
    return values


def descriptive(operation, series, weights=None):
    values = _numbers(series)
    n = len(values)
    preview = ", ".join(f"{v:g}" for v in values[:12]) + ("..." if n > 12 else "")
    if operation == "mean":
        result = sum(values) / n
        return {"name": "Media aritmética", "formula": "x̄ = Σxᵢ / n", "steps": [f"Valores válidos: {preview}", f"Σxᵢ = {sum(values):g}", f"n = {n}", f"x̄ = {sum(values):g} / {n}"], "result": result}
    if operation == "median":
        ordered = sorted(values)
        result = float(np.median(ordered))
        return {"name": "Mediana", "formula": "Md = valor central del conjunto ordenado", "steps": [f"Ordenar: {', '.join(f'{v:g}' for v in ordered[:12])}", f"n = {n}", "Tomar el valor central" if n % 2 else "Promediar los dos valores centrales"], "result": result}
    if operation == "mode":
        modes = pd.Series(values).mode().tolist()
        return {"name": "Moda", "formula": "Mo = valor(es) con mayor frecuencia", "steps": [f"Contar frecuencias de: {preview}", f"Frecuencia máxima = {max(values.count(v) for v in set(values))}"], "result": modes}
    if operation == "variance":
        mean = sum(values) / n
        result = sum((x - mean) ** 2 for x in values) / n
        return {"name": "Varianza poblacional", "formula": "σ² = Σ(xᵢ - μ)² / n", "steps": [f"μ = {mean:.6g}", "Calcular cada diferencia respecto de μ y elevarla al cuadrado", f"Σ(xᵢ - μ)² = {sum((x-mean)**2 for x in values):.6g}", f"Dividir entre n = {n}"], "result": result}
    if operation == "std":
        variance = descriptive("variance", values)
        return {"name": "Desviación estándar poblacional", "formula": "σ = √σ²", "steps": variance["steps"] + [f"σ = √{variance['result']:.6g}"], "result": math.sqrt(variance["result"])}
    if operation == "weighted_mean":
        weight_values = _numbers(weights)
        if len(weight_values) != n:
            raise ValueError("Valores y ponderaciones deben tener la misma cantidad de registros válidos.")
        total_weight = sum(weight_values)
        if total_weight == 0:
            raise ValueError("La suma de las ponderaciones no puede ser cero.")
        products = sum(x * w for x, w in zip(values, weight_values))
        return {"name": "Media ponderada", "formula": "x̄ₚ = Σ(xᵢwᵢ) / Σwᵢ", "steps": [f"Σ(xᵢwᵢ) = {products:.6g}", f"Σwᵢ = {total_weight:.6g}", f"x̄ₚ = {products:.6g} / {total_weight:.6g}"], "result": products / total_weight}
    raise ValueError("Operación estadística no permitida.")


def scalar(operation, value):
    number = float(value)
    if operation == "square":
        return {"name": "Cuadrado", "formula": "x² = x · x", "steps": [f"{number:g} · {number:g}"], "result": number ** 2}
    if operation == "sqrt":
        if number < 0:
            raise ValueError("La raíz real requiere un número mayor o igual que cero.")
        return {"name": "Raíz cuadrada", "formula": "y = √x, donde y² = x", "steps": [f"Buscar y tal que y² = {number:g}"], "result": math.sqrt(number)}
    raise ValueError("Operación escalar no permitida.")


def parse_matrix(text):
    rows = [[float(value.strip()) for value in line.split(",")] for line in text.strip().splitlines() if line.strip()]
    if not rows or len({len(row) for row in rows}) != 1:
        raise ValueError("La matriz debe ser rectangular; separa columnas con comas y filas con saltos de línea.")
    if len(rows) > 10 or len(rows[0]) > 10:
        raise ValueError("El límite es 10 × 10 para mantener una respuesta clara.")
    return np.array(rows, dtype=float)


def matrix(operation, matrix_a, matrix_b=None):
    a = parse_matrix(matrix_a)
    if operation == "transpose":
        result = a.T
        steps = [f"Intercambiar filas por columnas: A es {a.shape[0]}×{a.shape[1]}", f"Aᵀ es {result.shape[0]}×{result.shape[1]}"]
        formula = "(Aᵀ)ᵢⱼ = Aⱼᵢ"
    elif operation == "determinant":
        if a.shape[0] != a.shape[1]:
            raise ValueError("El determinante requiere una matriz cuadrada.")
        result = float(np.linalg.det(a))
        steps = [f"Verificar matriz cuadrada {a.shape[0]}×{a.shape[1]}", "Aplicar expansión/determinante numérico estable"]
        formula = "det(A)"
    elif operation == "inverse":
        if a.shape[0] != a.shape[1]:
            raise ValueError("La inversa requiere una matriz cuadrada.")
        if abs(np.linalg.det(a)) < 1e-12:
            raise ValueError("La matriz es singular y no tiene inversa.")
        result = np.linalg.inv(a)
        steps = [f"det(A) = {np.linalg.det(a):.6g} ≠ 0", "Aplicar eliminación de Gauss-Jordan", "Comprobar A · A⁻¹ = I"]
        formula = "A⁻¹ = adj(A) / det(A)"
    elif operation == "multiply":
        b = parse_matrix(matrix_b or "")
        if a.shape[1] != b.shape[0]:
            raise ValueError("Para multiplicar, las columnas de A deben igualar las filas de B.")
        result = a @ b
        steps = [f"A: {a.shape[0]}×{a.shape[1]}; B: {b.shape[0]}×{b.shape[1]}", "Multiplicar cada fila de A por cada columna de B y sumar productos"]
        formula = "(AB)ᵢⱼ = Σₖ AᵢₖBₖⱼ"
    else:
        raise ValueError("Operación matricial no permitida.")
    return {"name": {"transpose":"Transpuesta", "determinant":"Determinante", "inverse":"Matriz inversa", "multiply":"Producto matricial"}[operation], "formula": formula, "steps": steps, "result": result.tolist() if isinstance(result, np.ndarray) else result}
