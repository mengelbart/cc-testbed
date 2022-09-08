#!/usr/bin/env python

import argparse
import glob
import json
import multiprocessing
import shutil
import os
import yaml

import pandas as pd

from analyzers.pcap_analyzer import PCAPAnalyzer
from analyzers.flow_analyzer import SingleFlowAnalyzer
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


def read_capacity(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'bandwidth'],
        header=None,
        usecols=[0, 2],
    )


class SingleExperimentAnalyzer():
    def __init__(self, input_dir, output_dir):
        self._directory = input_dir
        self._output = output_dir
        self._plot_files = []
        self._aggregates = {}

    def analyze(self):
        files = [file for file in glob.glob(self._directory + '/**/*',
                 recursive=True) if os.path.isfile(file)]
        config = next((f for f in files if f.endswith('config.json')), None)
        if not config:
            print('config file not found, aborting analyses')
            return

        c = read_config_json(config)

        config_filename = os.path.join(self._output, 'config.json')
        with open(config_filename, 'w') as file:
            json.dump(c, file)

        self._config = c
        self._basetime = c.get('start_time')

        link_file = next((f for f in files if f.endswith('link.log')), None)
        if link_file:
            link = read_capacity(link_file)
            link.index = pd.to_datetime(link.index - self._basetime, unit='ms')

        flows = [flow for flow in c['flows']]
        flow_plots = []
        for flow in flows:
            if 'id' in flow:
                out = os.path.join(self._output, str(flow['id']))
                fa = SingleFlowAnalyzer(flow, out, self._basetime)
                fa.set_link_capacity(link)
                fa.analyze()
                fa.plot()
                flow_plots.append({
                    'id': str(flow['id']),
                    'plots': [{
                        'file_name': Path(pf).relative_to(Path(self._output)),
                    } for pf in fa.plot_files],
                })

        # self.analyze_pcap(files)

        self.save_aggregates()
        self.render_html(flow_plots)

    def analyze_pcap(self, files):
        pcap = next((f for f in files if f.endswith('ls1-eth1.pcap')), None)
        if pcap is None:
            return

        a = PCAPAnalyzer()
        a.read(pcap)

    def save_aggregates(self):
        filename = os.path.join(self._output, 'aggregates.json')
        with open(filename, mode='w', encoding='utf-8') as f:
            json.dump(self._aggregates, f)

    def render_html(self, flows):
        environment = Environment(loader=FileSystemLoader('templates/'))
        environment.filters['tojson_pretty'] = to_pretty_json
        template = environment.get_template('experiment.html')

        context = {
            'flows': flows,
            'config': self._config,
        }
        content = template.render(context)
        filename = os.path.join(self._output, 'index.html')
        with open(filename, mode="w", encoding="utf-8") as f:
            f.write(content)


def to_pretty_json(value):
    data = json.dumps(value, sort_keys=True,
                      indent=4, separators=(',', ': '))
    return data


class AggregateAnalyzer():
    def __init__(self, args):
        pass

    def analyze(self):
        pass


def read_config_yaml(path):
    file = Path(path)
    if file.is_file():
        with open(file) as f:
            c = yaml.safe_load(f)
    return c


def read_config_json(path):
    with open(path) as r:
        c = json.load(r)
    return c


def create_index(args):
    config_file = os.path.join(args.input_dir, 'config.yaml')
    if not os.path.isfile(config_file):
        print('config.yaml not found, aborting')

    main_configs = read_config_yaml(config_file)

    configs = []
    for name, config in main_configs.items():
        root_dir = os.path.join(args.input_dir, name)
        dirs = [d for d in glob.glob(root_dir + '/**', recursive=True)
                if os.path.isdir(d) and
                any(fname.endswith('config.json')
                    for fname in os.listdir(d))]
        paths = [{
            'path': Path(d).relative_to(args.output_dir),
            'config': read_config_json(os.path.join(d, 'config.json')),
        } for d in sorted(dirs)]
        if len(paths) == 0:
            continue

        e_headers = list(paths[0]['config']['emulation']['parameters'].keys())
        f_headers = []
        for i, f in enumerate(paths[0]['config']['flows']):
            f_headers.extend([f'f{i}-{f}' for f in f.get('parameters', [])])

        experiments = []
        for p in paths:
            emu_parameters = [
                p['config']['emulation']['parameters'][header]
                for header in e_headers
            ]
            flow_parameters = []
            for i, f in enumerate(p['config']['flows']):
                if 'parameters' not in f:
                    continue
                keys = [header.split(f'f{i}-') for header in f_headers]
                flow_parameters.extend([
                    f['parameters'].get(key[1], '')
                    for key in keys if len(key) > 1
                ])

            experiments.append({
                'link': os.path.join(p['path'], 'index.html'),
                'name': str(p['path']),
                'parameters': emu_parameters + flow_parameters,
            })

        configs.append({
            'root_config_name': name,
            'root_config': config,
            'headers': ['Link'] + e_headers + f_headers,
            'experiments': experiments,
        })

    environment = Environment(loader=FileSystemLoader('templates/'))
    template = environment.get_template('index.html')

    context = {
        'evaluated_configs': configs,
    }
    content = template.render(context)
    filename = os.path.join(args.output_dir, 'index.html')
    with open(filename, mode='w', encoding='utf-8') as f:
        f.write(content)


def run_single(args):
    Path(args['output_dir']).mkdir(parents=True, exist_ok=True)
    SingleExperimentAnalyzer(args['input_dir'], args['output_dir']).analyze()


def analyze_single(args):

    files = [f for f in glob.glob(args.input_dir + '**', recursive=True)
             if os.path.isfile(f)]
    main_config = next((f for f in files if f.endswith('config.yaml')), None)
    if main_config:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        shutil.copy(main_config, os.path.join(args.output_dir, 'config.yaml'))

    dirs = [d for d in glob.glob(args.input_dir + '**', recursive=True)
            if os.path.isdir(d) and
            any(fname.endswith('config.json') for fname in os.listdir(d))]

    pool = multiprocessing.Pool(16)
    args = [{
            'input_dir': dir,
            'output_dir': os.path.join(
                args.output_dir, str(Path(dir).relative_to(args.input_dir))),
            } for dir in dirs]
    pool.map(
        run_single,
        args,
    )


def analyze_aggregate(args):
    AggregateAnalyzer(args).analyze()


def main():
    parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    subparsers = parser.add_subparsers()
    single = subparsers.add_parser(
            'single',
            help='analyze a single experiment')
    single.set_defaults(func=analyze_single)

    aggregate = subparsers.add_parser(
            'aggregate',
            help='analyze a set of experiments')
    aggregate.set_defaults(func=analyze_aggregate)

    index = subparsers.add_parser(
            'index',
            help='create index HTML page')
    index.set_defaults(func=create_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
