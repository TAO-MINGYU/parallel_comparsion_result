#!/usr/bin/env python3
"""Produce standalone vector figures from the complete report CSV tables."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


METHODS = ('pysr', 'operon', 'dsr', 'ai_feynman_2', 'gplearn', 'tf4sr')
LABELS = ('PySR', 'Operon', 'DSR', 'AI-Feynman', 'gplearn', 'TF4SR')


def rows(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def save(fig, output, name):
    fig.savefig(output / (name + '.svg'), bbox_inches='tight', metadata={'Date': None})
    fig.savefig(output / (name + '.pdf'), bbox_inches='tight', metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


def plot(tables, output):
    tables, output = Path(tables), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 9, 'svg.fonttype': 'none', 'svg.hashsalt': 'external-b7-20261027', 'axes.spines.top': False,
                         'axes.spines.right': False, 'pdf.fonttype': 42})
    overall = {r['method']: r for r in rows(tables / 'overall.csv')}
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    x = np.arange(6)
    ax.bar(x - .18, [100 * int(overall[m]['primary_usable']) / int(overall[m]['registered']) for m in METHODS],
           .36, label='Usable / all registered')
    ax.bar(x + .18, [100 * int(overall[m]['primary_usable']) / int(overall[m]['applicable']) for m in METHODS],
           .36, label='Usable / applicable')
    ax.set_xticks(x, LABELS); ax.set_ylim(0, 105); ax.set_ylabel('Prediction coverage (%)')
    ax.legend(loc='lower left'); ax.set_title('Fixed-configuration external baselines: coverage, not accuracy')
    save(fig, output, 'prediction-coverage')
    tabular = [r for r in rows(tables / 'common_condition.csv') if r['kind'] == 'tabular']
    variants = ['clean', 'output_noise_01', 'output_noise_05', 'output_noise_10']
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5), sharey=True)
    for ax, track, label in zip(axes, ['constrained_resource', 'capability_ceiling'], ['120 s / scalar target', '900 s / scalar target']):
        for method, name in zip(METHODS, LABELS):
            lookup = {r['variant']: r for r in tabular if r['method'] == method and r['resource_track'] == track}
            ax.plot(range(4), [100 * float(lookup[v]['primary_nrmse_le_0.1_rate_all_applicable']) for v in variants],
                    marker='o', linewidth=1.2, label=name)
        ax.set_xticks(range(4), ['0%', '1%', '5%', '10%']); ax.set_xlabel('Added output noise')
        ax.set_title(label); ax.set_ylim(0, 100); ax.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('NRMSE <= 0.1 / common-applicable fits (%)')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=6, fontsize=8, loc='lower center',
               bbox_to_anchor=(.5, -.10), frameon=False)
    fig.suptitle('Tabular NRMSE: clean latent targets; observed targets for black-box data')
    save(fig, output, 'tabular-noise-attainment')
    ode = [r for r in rows(tables / 'ode-system-common-summary.csv') if r['variant'] != 'ALL']
    variants = sorted({r['variant'] for r in ode})
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 3.8), sharey=True)
    for ax, track, label in zip(axes, ['constrained_resource', 'capability_ceiling'], ['120 s / component', '900 s / component']):
        for method, name in zip(METHODS, LABELS):
            lookup = {r['variant']: r for r in ode if r['method'] == method and r['resource_track'] == track}
            rates = [100 * float(lookup[v]['primary_nrmse_le_0.1_rate_all_applicable'])
                     if lookup[v]['primary_nrmse_le_0.1_rate_all_applicable'] else float('nan') for v in variants]
            ax.plot(range(len(variants)), rates, marker='o', linewidth=1.2, label=name)
        ax.set_xticks(range(len(variants)), variants, rotation=25, ha='right', fontsize=7)
        ax.set_ylim(0, 100); ax.set_title(label); ax.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('System NRMSE <= 0.1 / common-applicable systems (%)')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=6, fontsize=8, loc='lower center',
               bbox_to_anchor=(.5, -.25), frameon=False)
    fig.suptitle('ODE: every component required; clean derivative prediction, not trajectory rollout')
    save(fig, output, 'ode-system-attainment')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--tables', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    plot(args.tables, args.output)
