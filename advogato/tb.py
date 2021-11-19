#!/usr/bin/python3

"""
This is a very simple testbench application. Run like so:

./tb.py [graph file] [experiment file]

Your graph file should be a serialized Digraph created with graphgen.py. Your experiment file 
should be a Python script. Your experiment file is executed in the current scope, so you can access
objects using the following identifiers:

advogato    the advogato.py module
h           the original Digraph as loaded from disk, before transformation to a flow network
g           the current state of the flow network
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

"""
Print the inedges and outedges (and corresponding flow) for flow network 'g' and original
(pre-transformed) vertex label 'u'
"""
def print_vertex_info(g, u):
  neg = advogato.Digraph.flow_net_get_vlabel_in(u)
  inedges = []

  for v in g.V:
    if neg in g.V[v]:
      inedges.append(f"{advogato.Digraph.flow_net_get_vlabel_orig(v)} ({g.V[v][neg].f})")    
  
  print(f"Vertex info for {u} ({g.V[neg][advogato.Digraph.flow_net_get_vlabel_out(u)].f})...")
  inedges = ", ".join(inedges)
  print(f"Inedges: {inedges}")
  
  pos = advogato.Digraph.flow_net_get_vlabel_out(u)
  outedges = []
  
  for v in g.V[pos]:
    outedges.append(f"{advogato.Digraph.flow_net_get_vlabel_orig(v)} ({g.V[pos][v].f})") 
  
  outedges = ", ".join(outedges)
  print(f"Outedges: {outedges}")

def print_graph_info(g):
  print("\nGraph info:")
  print(f"Vertices: {len(g.V)}")

# Print the top simulated peers by trust score
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
  
  g = recompute_trust(h)
  print_graph_info(g)
  print_top(g)
  print("\n*** BEGIN TEST ***\n")
  exec(open(experiment_path).read())

if __name__ == "__main__":
  main()
