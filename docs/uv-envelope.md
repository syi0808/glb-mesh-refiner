# UV-anchored geometric envelope

The refiner records a source mapping metric per input face and builds a spatial grid over nondegenerate input UV triangles. A UV lookup reconstructs the source 3D position by barycentric interpolation within the original face. Lookups outside the UV atlas or across overlapping charts that reconstruct different 3D positions are treated as unsafe. Faces with unprojectable or degenerate source mappings are pinned.

Before a collapse commits, each affected surviving face is sampled at its three corners, three edge midpoints, and centroid. Proposed positions must remain within the configured distance of the source UV-to-3D correspondence. UV determinant orientation must be unchanged, relative directional stretch must stay within the configured limit against the original face, and geometric/shading normals must pass their guards. The same checks run on both chart wedges of a synchronized seam collapse, with each chart's UVs evaluated separately.

This is a sampled engineering guard, not a continuous proof. A finite set of samples cannot guarantee an upper bound at unsampled points, detect all texture filtering/color discontinuities, or establish perceptual equivalence. Independent GLB validation and rendering in the target application remain important.

The edge-line QEM minimizer uses homogeneous coordinates correctly: for `x(t)=p+t*d`, the direction has `w=0` and the point has `w=1`, giving `A=dᵀQ₃×₃d` and `B=2d·(Q₃×₃p+q_xyz,w)`. It clamps `t` to `[0,1]` and compares with both endpoints. A translated-plane regression catches origin-dependent minimizer errors. QEM algebra does not by itself preserve local fullness, curvature, or texture appearance.
