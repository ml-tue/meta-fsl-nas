###############################################################################
# Copyright (c) Hayeon Lee, Eunyoung Hyung [GitHub MetaD2A], 2021
# Rapid Neural Architecture Search by Learning to Generate Graphs from
# Datasets, ICLR 2021
###############################################################################
import os
import igraph
import numpy as np
import scipy.stats
import torch


def load_graph_config(graph_data_name, nvt, data_path):
    if graph_data_name != 'nasbench201':
        raise NotImplementedError(graph_data_name)
    g_list = []
    max_n = 0  # maximum number of nodes
    ms = torch.load(os.path.join(
        data_path, f'{graph_data_name}.pt'))['arch']['matrix']
    for i in range(len(ms)):
        g, n = decode_NAS_BENCH_201_8_to_igraph(ms[i])
        max_n = max(max_n, n)
        g_list.append((g, 0))
    # number of different node types including in/out node
    graph_config = {}
    graph_config['num_vertex_type'] = nvt  # original types + start/end types
    graph_config['max_n'] = max_n  # maximum number of nodes
    graph_config['START_TYPE'] = 0  # predefined start vertex type
    graph_config['END_TYPE'] = 1  # predefined end vertex type

    return graph_config


def load_pretrained_model(model_path, model):
    model_path, name = os.path.split(model_path)
    assert name, "Specify the full path for argument 'model_path'."
    print(f"Loading pretrained model from {model_path}")

    state = torch.load(model_path)
    model.load_state_dict(state)


def save_model(save_path, model, epoch, max_corr=None):
    if max_corr is not None:
        torch.save(model.cpu().state_dict(),
                   os.path.join(save_path, 'predictor_max_corr.pt'))
    else:
        torch.save(model.cpu().state_dict(),
                   os.path.join(save_path, f'predictor_{epoch}.pt'))


def decode_NAS_BENCH_201_8_to_igraph(row):
    if isinstance(row, str):
        row = eval(row)  # convert string to list of lists
    n = len(row)
    g = igraph.Graph(directed=True)
    g.add_vertices(n)
    for i, node in enumerate(row):
        g.vs[i]['type'] = node[0]
        if i < (n - 2) and i > 0:
            g.add_edge(i, i + 1)  # always connect from last node
        for j, edge in enumerate(node[1:]):
            if edge == 1:
                g.add_edge(j, i)
    return g, n


def is_valid_NAS201(g, START_TYPE=0, END_TYPE=1):
    # first need to be a valid DAG computation graph
    res = is_valid_DAG(g, START_TYPE, END_TYPE)
    # in addition, node i must connect to node i+1
    res = res and len(g.vs['type']) == 8
    res = res and not (0 in g.vs['type'][1:-1])
    res = res and not (1 in g.vs['type'][1:-1])
    return res


def decode_igraph_to_NAS201_matrix(g):
    m = [[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0],
         [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]]
    xys = [(1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2)]
    for i, xy in enumerate(xys):
        m[xy[0]][xy[1]] = float(g.vs[i + 1]['type']) - 2
    return np.array(m)


def decode_igraph_to_NAS_BENCH_201_string(g):
    if not is_valid_NAS201(g):
        return None
    m = decode_igraph_to_NAS201_matrix(g)
    types = ['none', 'skip_connect', 'nor_conv_1x1',
             'nor_conv_3x3', 'avg_pool_3x3']
    return '|{}~0|+|{}~0|{}~1|+|{}~0|{}~1|{}~2|'.\
        format(types[int(m[1][0])],
               types[int(m[2][0])], types[int(m[2][1])],
               types[int(m[3][0])], types[int(m[3][1])], types[int(m[3][2])])


def is_valid_DAG(g, START_TYPE=0, END_TYPE=1):
    res = g.is_dag()
    n_start, n_end = 0, 0
    for v in g.vs:
        if v['type'] == START_TYPE:
            n_start += 1
        elif v['type'] == END_TYPE:
            n_end += 1
        if v.indegree() == 0 and v['type'] != START_TYPE:
            return False
        if v.outdegree() == 0 and v['type'] != END_TYPE:
            return False
    return res and n_start == 1 and n_end == 1
