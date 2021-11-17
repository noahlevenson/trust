#!/usr/bin/python3

"""
This tool generates a simple random trust graph and writes it to disk such that it can be loaded
in the testbench. By "simple," we mean that it generates trust graphs which are purely hierarchical,
having no backedges or cycles (i.e., a tree). In the spirit of reducing cognitive overhead during 
experimentation, vertices are assigned human names according to their distance from the seed: 
vertices at distance 1 from the seed get an 'A' name, vertices at distance 2 get a 'B' name...
"""

import advogato
import tb
import random
import json
import string
import pickle
import uuid

OUTPUT_DIR = "graphs"

"""
Hyperparameters: When considering the graph as a tree, 'max_depth' is the max distance from the
seed at which we will generate vertices; 'max_children' is the max number of outedges each vertex
can have (corresponding to the max number of signatures issued by that peer).
"""
max_depth = 8
max_children = 4

# Here we create a dictionary where each key is a lowercase letter mapping to a list of first names...
with open("first-names.json") as f:
  first = json.load(f)

names = dict(zip(list(string.ascii_lowercase), [[] for _ in range(len(string.ascii_lowercase))]))

for name in first:
  names[name[0].lower()].append(name)

# By combining a first name with a middle name, we expand the name space...
with open("middle-names.json") as f:
  middle = json.load(f)

# Map integers [0, 26] to lowercase letters such that we can fetch a letter by distance from seed
alpha_index = dict(zip(range(len(string.ascii_lowercase)), list(string.ascii_lowercase)))

if max_depth > len(string.ascii_lowercase):
  raise ValueError(f"Things break if 'max_depth' exceeds {len(string.ascii_lowercase)}")

"""
Recursive function to generate a random graph. To generate a new graph, create a Digraph with 
one seed vertex; pass the Digraph as 'g' and the vertex label for the seed as 'v'
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

    g.add_edge(v, advogato.Edge(child_name))
    add_children(g, child_name, depth + 1)

"""

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DRIVER CODE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""

h = advogato.Digraph()
h.add_vertex("seed")
add_children(h, "seed")
g = tb.recompute_trust(h)

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
tb.print_top(g)
