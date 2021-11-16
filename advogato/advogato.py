#!/usr/bin/python3

""" 
This is the Advogato trust metric, based on max flow using Ford-Fulkerson and BFS, plus some 
fancyish tooling to make it easier to perform experiments and reason about the results. 
"""

import random
import os
import json
import string
import pickle
import uuid
from enum import IntEnum
from functools import partial

OUTPUT_DIR = "graphs"

# Discovery colors for graph search algos, we don't need em but they're nice for debugging
class COLOR(IntEnum):
  WHITE = 0
  GREY = 1
  BLACK = 2

# A vertex property for graph search algos
class Vertex_prop:
  def __init__(self, color, d, pi, label):
    self.color = color
    self.d = d
    self.pi = pi
    self.label = label

  def __str__(self):
    return (f"Vertex_prop(color: {self.color}, d: {self.d}, pi: " + 
      f"{None if self.pi == None else self.pi.label}, label: {self.label})")

# Data structure for a directed graph
class Digraph():
  def __init__(self):
    self.V = {}

  def __str__(self):
    return "\n".join([v + ": " +  ", ".join([str(self.V[v][key]) for key in self.V[v]]) for v in self.V])
  
  """
  Factory method to build a flow network based on the Advogato spec. 'vcaps' is a dictionary where 
  each key is a vertex label which maps to a capacity as an integer. 'source_label' is a string
  corresponding to a vertex which you should have already created. (It will get relabeled as part
  of this process.) 'supersink_label' is a string; we'll create that vertex for you. If this 
  Digraph has antiparallel edges, we will fix them up. Returns a 2-tuple: (Digraph, new source label)
  """
  def to_flow_net(self, vcaps, source_label, supersink_label):
    ap_vertices = self._fix_antiparallel(vcaps)
    g = Digraph()

    for v in self.V:
      in_vertex = f"{v}_IN"
      out_vertex = f"{v}_OUT"
      # If there's no entry for this vertex in the vertex capacities table, it's beyond the 
      # maximum distance we set capacities for, so assign it a capacity of 0
      cap = vcaps[v] - 1 if v in vcaps else 0
      g.add_edge(in_vertex, Edge(v=out_vertex, c=cap, vertex_id=v))
      
      # Don't add a unit edge for the "virtual" nodes we created while fixing antiparallel edges
      if v not in ap_vertices:
        g.add_edge(in_vertex, Edge(supersink_label, 1))

      for u in self.V[v]:
        g.add_edge(out_vertex, Edge(f"{u}_IN", float("inf")))
    
    return (g, f"{source_label}_IN")
    
  # Fix antiparallel edges per CLRS p. 711; returns a set of labels corresponding to the added vertices
  def _fix_antiparallel(self, vcaps):
    new_vertices = set()

    for v in self.V.copy():
      for u in self.V[v]:
        if v in self.V[u]:
          prime = f"ANTIPARALLEL_{u}->{v}"
          new_vertices.add(prime)
          self.add_edge(u, Edge(prime))
          self.add_edge(prime, Edge(v))
          self.del_edge(u, v)
          # The added vertex gets a capacity of infinity, since it's a "virtual" node, i.e. it 
          # doesn't actually represent an entity in our graph, it's basically just a fancy edge
          vcaps[prime] = float("inf")

    return new_vertices

  """
  Breadth first search. Optional function 'skip' is called for each edge (u, v) during graph
  exploration; if it returns True, edge (u, v) will not be explored. Pass 's' as string corresponding
  to vertex label. Returns a predecessor subgraph as a dictionary of Vertex_prop objects.
  """
  def bfs(self, s, skip=None):
    vprops = {}

    for v in self.V:
      # Don't include props for the source vertex
      if v == s:
        vprops[s] = None
        continue
      
      vprops[v] = Vertex_prop(COLOR.WHITE, float("inf"), None, v)

    sp = Vertex_prop(COLOR.GREY, 0, None, s)
    q = []
    q.append(sp)

    while len(q) != 0:
      u = q.pop(0)

      for key in self.V[u.label]:
        edge = self.V[u.label][key]
        
        if skip and skip(u.label, key):
          continue

        vp = vprops[edge.v] if vprops[edge.v] != None else sp

        if vp.color == COLOR.WHITE:
          vp.color = COLOR.GREY
          vp.d = u.d + 1
          vp.pi = u
          q.append(vp)

      u.color = COLOR.BLACK

    vprops[sp.label] = sp
    filtered = [vp for vp in vprops.values() if vp.pi != None or vp == sp]
    return dict(zip([vprop.label for vprop in filtered], filtered))

  # Idempotently add vertex 'u'
  def add_vertex(self, u):
    if u not in self.V:
      self.V[u] = dict()

  # Idempotently add an outedge from vertex u, represented by Edge object 'e'. Caller must be sure
  # to create and configure the Edge object correctly!
  def add_edge(self, u, e):
    if u not in self.V:
      self.V[u] = dict()

    self.V[u][e.v] = e

    if e.v not in self.V:
      self.V[e.v] = dict()

  def del_edge(self, u, v):
    del self.V[u][v]

  def has_edge(self, u, v):
    if u in self.V and v in self.V[u]:
      return True
    else:
      return False

"""
Data structure for a directed edge in a flow network to vertex 'v' with capacity 'c'. We use 
'vertex_id' to differentiate edges which represent vertex capacities from those which represent
edges between vertices. TODO: this should really subclass an Edge base class which doesn't concern
itself with flow network-specific concepts like "capacity" and "flow"...
"""
class Edge():
  def __init__(self, v, c=0, f=0, vertex_id=None):
    self.v = v
    self.c = c
    self.f = f
    self.vertex_id = vertex_id

  def __str__(self):
    return f"{self.v} ({self.f}/{self.c})"

"""
per CLRS p. 725, this function produces a graph data structure G' of input G, where G' has
all the edges of G and all the transposed edges of G. This allows us to represent G and its
residual network in a single data structure which we can update efficiently during the main loop
of Ford-Fulkerson, as opposed to recomputing a new residual network data structure on each 
iteration. Note that the residual network of G' consists of the edges (u, v) of G' such that
the residual capacity of (u, v) > 0.
"""
def _optimize(g):
  g_prime = Digraph()
  
  for vertex_key in g.V:
    for edge_key in g.V[vertex_key]:
      edge = g.V[vertex_key][edge_key]
      g_prime.add_edge(vertex_key, Edge(edge.v, edge.c))
      g_prime.add_edge(edge.v, Edge(vertex_key, edge.f))
  
  return g_prime

# Compute the residual capacity for edge ('u', 'v') in graph 'g'
def res_cap(g, u, v):
  if g.has_edge(u, v):
    return g.V[u][v].c - g.V[u][v].f
  elif g.has_edge(v, u):
    return g.V[v][u].f
  else:
    return 0

# Edge skip function for BFS: skip edges with a residual capacity of zero
def _has_zero_res_cap(g, u, v):
  return res_cap(g, u, v) == 0

# Compute max flow over Flow_network 'g', source vertex label 's' and sink vertex label 't'
def ford_fulkerson(g, s, t):
  g_prime = _optimize(g)
  pg = g_prime.bfs(s, partial(_has_zero_res_cap, g))
  
  # Since we used BFS, the path from the source to the sink is the shortest path
  while t in pg:
    # Collect the path from s to t as a list of tuples of edge labels in reverse order
    path = []
    vprop = pg[t]

    while vprop.pi != None:
      path.append((pg[vprop.pi.label].label, vprop.label))
      vprop = vprop.pi
    
    # Compute cfp aka the residual capacity of the path
    cfp = float("inf")
    
    # Print each augmenting path during the main loop...
    _ = os.system("clear")
    print("Augmenting path: ")
    # Reversing the path isn't necessary for correctness, but it prints nicer this way
    path.reverse()
    print(path)

    for edge in path:
      u, v = edge
      new_cfp = res_cap(g_prime, u, v)
      
      if new_cfp < cfp:
        cfp = new_cfp
     
    for edge in path:
      u, v = edge
      
      # For each case, we update the optimizing data structure G' and also the original graph G
      if g.has_edge(u, v):
        g_prime.V[u][v].f += cfp
        g_prime.V[v][u].c = g_prime.V[u][v].f # Update the transposed edge
        g.V[u][v].f += cfp
      else:
        g_prime.V[v][u].f -= cfp
        g_prime.V[u][v].c = g_prime.V[v][u].f # Update the transposed edge
        g.V[v][u].f -= cfp

    pg = g_prime.bfs(s, partial(_has_zero_res_cap, g))

"""
To make it easier to reason about networks, let's assign each vertex a human name. And to make it
even easier to reason about networks, let's encode some semantics: all vertices at distance 1
from the seed will have an 'A' name, all vertices at distance 2 will have a 'B' name, and so on.
Here we create a dictionary where each key is a lowercase letter mapping to a list of first names...
"""
with open("first-names.json") as f:
  first = json.load(f)

# By combining a first name with a middle name, we expand the name space
with open("middle-names.json") as f:
  middle = json.load(f)

names = dict(zip(list(string.ascii_lowercase), [[] for _ in range(len(string.ascii_lowercase))]))

for name in first:
  names[name[0].lower()].append(name)

"""
Hyperparameters: When considering the graph as a tree, 'max_depth' is the max distance from the
seed at which we will generate vertices; 'max_children' is the max number of outedges each vertex
can have (corresponding to the max number of signatures issued by that peer).
"""
max_depth = 8
max_children = 4

# Map depth integers 0-26 to lowercase letters
alpha_index = dict(zip(range(len(string.ascii_lowercase)), list(string.ascii_lowercase)))

if max_depth > len(string.ascii_lowercase):
  raise ValueError(f"Things break if 'max_depth' exceeds {len(string.ascii_lowercase)}")

"""
In our early stages of experimentation, we want to observe the behaviors of simple trust graphs.
We use this recursive function to generate a purely hierarchical trust graph with no backedges. 
(i.e., a tree). Vertices receive human names in the manner described above.
"""
def add_children(g, v, depth=1):
  # Base case: we've reached our maximum depth, we're done here
  if depth == max_depth:
    return

  # Recursive case: add a random number of children [1, max_children]
  n_children = random.randint(1, max_children)
  
  for _ in range(n_children):
    first_name = random.choice(names[alpha_index[depth - 1]])
    middle_name = random.choice(middle)
    child_name = f"{first_name} {middle_name}"
    
    # Dumb unoptimized way to avoid name collisisons
    while child_name in g.V:
      middle_name = random.choice(middle)
      child_name = f"{first_name} {middle_name}"

    g.add_edge(v, Edge(child_name))
    add_children(g, child_name, depth + 1)

"""

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Driver code below

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""

# Recursively generate a graph with no backedges using the hyperparameters above
h = Digraph()
h.add_vertex("seed")
add_children(h, "seed")

"""
Capacity table: capacity for distance zero is equal to the number of "good" peers in the network, 
each successive distance is equal to the previous distance divided by the average outdegree.
TODO: Could we/should we generate this dynamically instead?
"""
caps = {
  0: 500,
  1: 200,
  2: 60,
  3: 30,
  4: 10,
  5: 3,
  6: 1
}

# Compute vertex capacities based on distance from the seed
pg = h.bfs("seed")
vcaps = dict(zip(pg.keys(), [caps[vprop.d] if vprop.d in caps else 1 for vprop in pg.values()]))

# Transform to a flow network, do Ford-Fulkerson and compute trust scores
g, new_source_label = h.to_flow_net(vcaps, "seed", "supersink")
ford_fulkerson(g, new_source_label, "supersink")

# Generate a graph ID, pickle it off and display the pertinent stuff
graph_id = uuid.uuid4()
output_path = f"./{OUTPUT_DIR}/{graph_id}.graph"

print("\nGraph info:")
print(f"ID: {graph_id}")
print(f"Vertices: {len(h.V)}")

n_outedges = 0
n_vertices = 0

for v in h.V:
  outdegree = len(h.V[v])
  
  if outdegree > 0:
    n_outedges += outdegree
    n_vertices += 1

print(f"Mean outdegree (not including leaf nodes): {n_outedges / n_vertices}")

with open(output_path, "wb") as f:
  pickle.dump(h, f)

print(f"\nSaved to {output_path}")
"""
Produce a list of (u, v, vertex_id, flow) 4-tuples, sorted by flow. Here's where we put that 
'vertex_id' property to use; we filter on it to select only the edges corresponding to vertices
"""
edges = [(vlabel, edge.v, edge.vertex_id, edge.f) for vlabel in g.V.keys() for edge in g.V[vlabel].values() if edge.vertex_id]
edges.sort(reverse=True, key=lambda x: x[3])

# Print top scores
n_show = 20
print(f"\nTop {n_show} peers by trust:")

for i, edge in enumerate(edges[0:n_show]):
  u, v, vertex_id, f = edge
  print(f"{i + 1}. {vertex_id}, {f}")
