# Synchronized UV-seam collapse

## Why this stage exists

GLB render vertices carry a position and per-vertex attributes together. A UV seam commonly duplicates a geometric point into two or more render vertices, each with its own UV coordinate. Treating those duplicates as separate topology can make a simplifier either stop at the seam or distort one chart independently. Welding them would lose the UV discontinuity.

This implementation therefore keeps the render vertices and faces separate. It builds a temporary position-only analysis topology using exact source-position keys, and only considers an unambiguous, two-sided seam edge whose two endpoint positions each have exactly two live attribute wedges.

## Atomic collapse rules

For a candidate geometric edge:

1. The edge must have exactly two incident faces, and both endpoint groups must pair exactly with those two face uses. Any nonmanifold edge in the affected one-ring, coincident duplicate faces, opposing sheets, or an ambiguous three-or-more-wedge position is rejected. Open-boundary endpoints remain pinned.
2. Any open-boundary, invalid-UV, small-component, or flagged-protrusion hard pin vetoes the candidate. The usual geometric link condition and duplicate-face checks are applied.
3. QEM cost and the placement are computed from the sum of the quadrics from both endpoint wedges on both charts. One XYZ placement is used for the paired wedges. Each chart interpolates its own UV and normal values; UVs are never averaged across charts.
4. Affected surviving faces must keep UV determinant orientation, remain within the configured relative directional-stretch limit against the source face, pass the sampled original-UV geometric-envelope guard, and pass geometric/shading-normal checks. Degenerate or duplicate faces reject the transaction.
5. The proposal is also checked for duplicate geometric face triples across the affected and unaffected mesh, including cases where render-index triples differ but their positions coincide. The two faces incident to the collapsed geometric edge are removed. All surviving source face/material associations and chart-specific attributes remain attached to their original wedge indices.

The stage is transactional: it tests a candidate first and changes positions, UVs, normals, faces, and quadrics only after all affected faces pass. The regular topology simplifier runs first; the synchronized pass then addresses otherwise locked, paired seam edges until the target is met or no safe candidate remains.

## Test coverage

`make test` includes a synthetic 12-by-12 grid with one split UV chart. The test requires at least one accepted synchronized collapse, checks that each acceptance removes exactly two incident faces, and verifies that output vertices at coincident seam positions still carry distinct UVs. Additional tests retain a seam with three coincident wedges and reject collapse across two fully coincident duplicate shells. Other pipeline tests cover embedded-image/material preservation, small detached components, flagged attached spikes, invalid input, and UV envelope/QEM math.

## Relation to published work and limitations

The temporary position remap and wedge-pair approach is informed by meshoptimizer's simplifier, which handles attribute-split vertices through position remapping and classifies ambiguous seam cases conservatively. Liu et al.'s *Seamless* work gives stronger seam conditions, including geometric and UV link conditions and compatibility requirements for neighboring seam edges. This code is a small standalone adaptation, not a port or a complete implementation of either algorithm. In particular, it does not implement the paper's complete collinearity and matching edge-length-ratio tests, nor does it compare texture colors sampled on both sides of a seam. A geometrically safe synchronized collapse can therefore still change a small region of texture appearance; verify the exported GLB in the target renderer.

The seam key is exact source position, not a persistent seam ID. Completely coincident shells with ordinary duplicate triangulation are blocked by edge-use/coincident-face guards and covered by tests, but adversarial overlapping geometry or numerically near-coincident positions are not semantically classified. Non-exact seam coordinates are not paired. The sampled UV envelope is also a finite sample guard, not a continuous proof.

