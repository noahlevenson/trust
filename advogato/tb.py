#!/usr/bin/python3

"""
This is a very simple testbench application. Run like so:

./tb.py [graph file] [experiment file]

Your graph file should be a serialized Digraph created with graphgen.py. Your experiment file 
should be a Python script. Your experiment file is executed in the current scope, so you can access
the Digraph using the 'h' identifier and Advogato functions using the 'advogato' identifier.
"""

import advogato
import sys
import pickle
from os.path import exists

GRAPHS_DIR = "graphs"
EXPERIMENTS_DIR = "experiments"

"""
Capacity table: capacity for distance zero is equal to the number of "good" peers in the network, 
each successive distance is equal to the previous distance divided by the average outdegree.
TODO: Could we/should we generate this dynamically instead?
"""
CAPS = {
  0: 500,
  1: 200,
  2: 60,
  3: 30,
  4: 10,
  5: 3,
  6: 1
}

# Transform Digraph 'h' into a flow network, recompute trust, and return the transformed graph 
def recompute_trust(h):
  pg = h.bfs("seed")
  vcaps = dict(zip(pg.keys(), [CAPS[vprop.d] if vprop.d in CAPS else 1 for vprop in pg.values()]))
  g, new_source_label = h.to_flow_net(vcaps, "seed", "supersink")
  advogato.ford_fulkerson(g, new_source_label, "supersink")
  return g

def print_top(g, n_show=20):
  """
  Produce a list of (u, v, vertex_id, flow) 4-tuples, sorted by flow. Here's where we put that
  'vertex_id' property to use (we filter on it to select only the edges corresponding to vertices).
  """
  edges = [(vlabel, edge.v, edge.vertex_id, edge.f) 
    for vlabel in g.V.keys() for edge in g.V[vlabel].values() if edge.vertex_id]
  
  edges.sort(reverse=True, key=lambda x: x[3])

  print(f"\nTop {n_show} peers by trust:")

  for i, edge in enumerate(edges[0:n_show]):
    u, v, vertex_id, f = edge
    print(f"{i + 1}. {vertex_id}, {f}")

def main():
  if len(sys.argv) < 3:
    print("Usage error: try ./tb.py [graph file] [experiment file]")
    sys.exit()

  graph_path = f"./{GRAPHS_DIR}/{sys.argv[1]}"

  if not exists(graph_path):
    print(f"Error: graph {graph_path} does not exist!")
    sys.exit()

  experiment_path = f"./{EXPERIMENTS_DIR}/{sys.argv[2]}"

  if not exists(experiment_path):
    print(f"Error: experiment {experiment_path} does not exist!")
    sys.exit()

  with open(graph_path, "rb") as f:
    h = pickle.load(f)
  
  print_top(recompute_trust(h))
  print("\n*** BEGIN TEST ***")
  exec(open(experiment_path).read())

if __name__ == "__main__":
  main()
