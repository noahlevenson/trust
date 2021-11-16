#!/usr/bin/python3

""" 
Here we modify vanilla Ford-Fulkerson to work over flow networks which implement vertex capacities.
This is achieved without significant modification by simply converting a graph with vertex 
capacities to one with edge capacities: https://cseweb.ucsd.edu/classes/sp16/cse202-a/hw3sol.pdf
"""

from enum import IntEnum

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

"""
Breadth first search with a twist: when traversing the graph, we do not explore edges with a 
residual capacity of zero. This lets us operate over the optimizing data structure G' and consider 
only the edges which represent the residual network of G. Pass 'g' as Flow_network, source 's' as string 
corresponding to vertex label. Returns a predecessor subgraph as a dictionary of Vertex_prop objects
"""
def bfs(g, s):
  vprops = {}

  for v in g.V:
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

    for key in g.V[u.label]:
      edge = g.V[u.label][key]
      
      # Skip edges with a residual capacity of zero
      if res_cap(g, u.label, key) == 0:
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

# Data structure for a flow network with edge capacities
class Flow_network():
  def __init__(self):
    self.V = {}

  def __str__(self):
    return "\n".join([v + ": " +  ", ".join([str(self.V[v][key]) for key in self.V[v]]) for v in self.V])
  
  """
  Factory method to build a flow network from a directed graph with vertex capacities. 'adj_list' is
  an adjacency list represented as a dictionary, where each key is a vertex label which maps to a 
  list of edge labels as strings. 'capacities' is a dictionary where each key is a vertex label
  which maps to a capacity as an integer. Beware, we perform no validation!
  
  Exciting and new: if your digraph has antiparallel edges, we'll fix them up for you!

  In transforming vertex capacities to edge capacities, we add vertices and relabel things: if your 
  source vertex was labeled 's', it's now 's_IN'; if your sink is 't', it's now 't_OUT'.
  """
  def from_vcap_graph(adj_list, capacities):
    Flow_network._fix_antiparallel(adj_list, capacities)
    g = Flow_network()
    
    for vertex_label in adj_list:
      in_vertex = f"{vertex_label}_IN"
      out_vertex = f"{vertex_label}_OUT"
      g.add_vertex(in_vertex)
      g.add_vertex(out_vertex)
      g.add_edge(in_vertex, out_vertex, capacities[vertex_label])

      for edge_label in adj_list[vertex_label]:
        g.add_edge(out_vertex, f"{edge_label}_IN", float("inf"))
    
    return g
  
  def _fix_antiparallel(adj_list, capacities):
    for v in adj_list.copy():
      for u in adj_list[v]:
        if v in adj_list[u]:
          prime = f"ANTIPARALLEL_{u}->{v}"
          adj_list[u].append(prime)
          adj_list[prime] = [v]
          adj_list[u].remove(v)
          # The added vertex gets a capacity of infinity, since it's a "virtual" node, i.e. it
          # doesn't actually represent an entity in our graph, it's basically just a fancy edge
          capacities[prime] = float("inf")

  # Idempotently add vertex 'u'
  def add_vertex(self, u):
    if u not in self.V:
      self.V[u] = dict()

  # Idempotently add an edge from vertex 'u' to vertex 'v' with capacity 'c'
  def add_edge(self, u, v, c):
    if u not in self.V:
      self.V[u] = dict()

    self.V[u][v] = Edge(v, c)

    if v not in self.V:
      self.V[v] = dict()
  
  def has_edge(self, u, v):
    if u in self.V and v in self.V[u]:
      return True
    else:
      return False

# Data structure for a directed edge in a flow network to vertex 'v' with capacity 'c'
class Edge():
  def __init__(self, v, c, f=0):
    self.v = v
    self.c = c
    self.f = f

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
  g_prime = Flow_network()
  
  for vertex_key in g.V:
    for edge_key in g.V[vertex_key]:
      edge = g.V[vertex_key][edge_key]
      g_prime.add_edge(vertex_key, edge.v, edge.c)
      g_prime.add_edge(edge.v, vertex_key, edge.f)
  
  return g_prime

# Compute the residual capacity for edge ('u', 'v') in graph 'g'
def res_cap(g, u, v):
  if g.has_edge(u, v):
    return g.V[u][v].c - g.V[u][v].f
  elif g.has_edge(v, u):
    return g.V[v][u].f
  else:
    return 0
  
# Compute max flow over Flow_network 'g', source vertex label 's' and sink vertex label 't'
def ford_fulkerson(g, s, t):
  g_prime = _optimize(g)
  pg = bfs(g_prime, s)

  while t in pg:
    # Collect the path from s to t as a list of tuples of edge labels in reverse order
    path = []
    vprop = pg[t]

    while vprop.pi != None:
      path.append((pg[vprop.pi.label].label, vprop.label))
      vprop = vprop.pi
    
    # Compute cfp aka the residual capacity of the path
    cfp = float("inf")
    
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

    pg = bfs(g_prime, s)

h = {
  "s": ["v1", "v2"],
  "v1": ["v3", "v2"],
  "v2": ["v1", "v4"],
  "v3": ["v2", "t"],
  "v4": ["v3", "t"],
  "t": []
}

h_cap = {
  "s": 800,
  "v1": 200,
  "v2": 200,
  "v3": 100,
  "v4": 100,
  "t": float("inf")
}

g = Flow_network.from_vcap_graph(h, h_cap)
ford_fulkerson(g, "s_IN", "t_OUT")
print(g)
