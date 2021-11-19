#!/usr/bin/python3

"""
Tested with: b702cf39-d265-4b56-8e54-5f968989dcd6.graph

In this experiment, an adversary attacks a high value peer (Carola Gene, the #16 most trusted
peer in the network), tricking them into assigning trust. The adversary then creates a nest
of 500 sock accounts and assigns trust to each of them.

A few observations:

1. Since the total quantity of flow that a peer can distribute is finite, the adversary causes 
their siblings -- that is, the other peers who have been assigned trust by Carola Gene -- to 
receive less flow. Delphine Kale's trust score is reduced from 10 to 4, while the adversary 
recieves 10.

2. The conservation of flow stipulates that a peer can only receive a quantity of flow equal to
the quantity of flow which they can send out. Given that each peer "drains" 1 unit of flow to 
the supersink via their negative vertex, a peer's outbound flow rate is constrained by their number
of successors. In other words: A new peer who doesn't trust anyone can at most receive 1 unit
of flow, since they only have a single path of capacity 1 to the supersink. Consequently, the
adversary actually receives a small reward for creating some number of sock accounts; in this case,
the first 10 sock accounts created by the adversary actually raise their trust score from 1 to 10.

3. The trust metric behaves as it should with respect to mitigating the impact of the Sybil attack:
of the 500 sock accounts created by the adversary, only 9 of them receive any flow at all, and
they each only receive 1 unit.
"""

# Apply this experiment to any graph by changing 'TARGET' to match a desired vertex label
TARGET = "Carola Gene"
ADVERSARY = "Adversary"

# Show initial state for the network
print_vertex_info(g, TARGET)
print("")

# Adversary tricks target into assigning trust
h.add_edge(TARGET, advogato.Edge(ADVERSARY))
g = recompute_trust(h)

# How has this affected the network?
print_graph_info(g)
print_top(g)
print("")
print_vertex_info(g, TARGET)
print("")
print_vertex_info(g, ADVERSARY)

# Adversary assigns trust to a nest of 500 sock accounts
for i in range(500):
  h.add_edge(ADVERSARY, advogato.Edge(f"Sock {i}"))
  
g = recompute_trust(h)

# How has this affected the network?
print_graph_info(g)
print_top(g)
print("")
print_vertex_info(g, TARGET)
print("")
print_vertex_info(g, ADVERSARY)
