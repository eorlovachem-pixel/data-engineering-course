"""Deterministic publication-quality summary figures for cleaned contacts."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

PALETTE = ["#164e63", "#0891b2", "#7c3aed", "#c2410c", "#16a34a", "#b45309"]


def save_figures(df: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook", palette=PALETTE)
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
    files: list[Path] = []

    by_station = df.groupby("station_name", observed=True)["transferred_gb"].sum().sort_values()
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    ax.barh(by_station.index, by_station.values, color=PALETTE[1])
    ax.set(xlabel="Transferred data (GB)", ylabel="Ground station", title="Downlink data by station")
    path = output / "01_downlink_by_station.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    files.append(path)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout="constrained")
    sns.histplot(data=df, x="snr_db", hue="link_status", bins=35, ax=axes[0, 0], alpha=0.65)
    axes[0, 0].set_title("SNR distribution by link outcome")
    sns.scatterplot(
        data=df.sample(n=min(1100, len(df)), random_state=2026),
        x="elevation_deg", y="slant_range_km", hue="rain_class",
        ax=axes[0, 1], s=22, alpha=0.55,
    )
    axes[0, 1].set_title("Elevation vs. slant range")
    daily = df.groupby("contact_date", as_index=False)["transferred_gb"].sum()
    sns.lineplot(data=daily, x="contact_date", y="transferred_gb", ax=axes[1, 0], marker="o")
    axes[1, 0].tick_params(axis="x", labelrotation=45)
    axes[1, 0].set_title("Daily transmitted volume")
    corr = df[["snr_db", "elevation_deg", "slant_range_km", "rain_rate_mm_h", "capacity_mbps"]].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", vmin=-1, vmax=1, cmap="BrBG", ax=axes[1, 1])
    axes[1, 1].set_title("Pearson correlations")
    path = output / "02_eda_dashboard.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    files.append(path)
    return files
