bleMD OVITO modifier nodes

In the bleMD editor, use Add (Shift+A) to choose a modifier from the same
categories used by your installed OVITO. Connect File Source → modifier(s) →
Particle Output; the graph updates automatically. Particle analyses also expose typed result
fields that can feed visualization on separate branches; see
[Particle fields](particle-fields.md). Enable **Expose full dataset** on these
analyses when you want to keep chaining their Data output. Nodes can be reordered by reconnecting them;
unchecking Enabled bypasses a modifier. Existing OVITO Script nodes still work
alongside native modifier nodes.

The catalog is discovered from the installed `ovito.modifiers` module at add-on
registration. Native display names and categories come from OVITO metadata.
Python-based ModifierInterface implementations are included. Abstract base
classes are excluded, and deprecated aliases share the canonical node type.
Modifiers introduced in a newer OVITO release are not advertised as available
in an older installation. Restart Blender after changing the OVITO package.

**Parameters.** Scalar, boolean, enum, vector, color, and matrix parameters have
Blender controls. Editing a value automatically enables its override checkbox;
unchecking the box restores OVITO's default initialization behavior. This is
important for properties and ranges that OVITO chooses based on the input data.
The displayed unchecked value is the constructor default, which may differ from
the value OVITO initializes when the modifier is connected to data.

Parameters on the node cover its primary settings. The selected node's sidebar
(N → Node) also exposes nested settings, such as visual elements and structure
type options. Collections use JSON: for example, Select type's Types can be
`[1, 2]` or `["Cu", "Ni"]`; Replicate's Operate on can be `["particles"]`.
OVITO validates which targets are supported by each modifier.
Matrices are flattened row by row. Optional interval fields use `null` or
`[start, end]`. Parameters have stable storage keys derived from their native
paths, so adding another parameter does not shift saved values to the wrong
control.

**Advanced configuration.** Every modifier has a Configuration text selector
and New Configuration button. Edit this text in Blender's Text Editor. It runs
after this node's modifier has been added, with `modifier` referring to the actual
OVITO modifier and `pipeline` containing the upstream chain through this node.
Use it for methods, complex collections, reference-source options, custom color
gradients, or settings not expressible as ordinary controls. For example, a
Create bonds node can use:

```python
from ovito.modifiers import CreateBondsModifier
modifier.mode = CreateBondsModifier.Mode.Pairwise
modifier.set_pairwise_cutoff(1, 2, 2.5)
```

**Files and Python.** Combine datasets and Load trajectory have a Source file
picker. Atomic strain, Displacement vectors, and Wigner-Seitz analysis have a
Reference file picker; leaving it empty retains OVITO's native reference
behavior. File paths may be Blender-relative (`//...`).

The Python script modifier accepts a Python Text defining `modify(frame, data)`:

```python
import numpy as np

def modify(frame, data):
    data.particles_.create_property(
        "Distance", data=np.linalg.norm(data.particles.positions, axis=1))
```

This function participates in OVITO evaluation and runs for requested frames.
The existing OVITO Script node instead configures an entire pipeline when the
recipe changes or on manual Update. Configuration texts similarly configure a modifier; they are not
per-frame particle functions. All three mechanisms execute normal Python.

**Manual selection.** Enter comma-separated Particle IDs and a Selection Frame.
The node records the selection through OVITO's native ManualSelectionModifier,
so IDs remain selected as the trajectory changes. Missing IDs produce an error.
This version does not provide OVITO-style interactive picking in the Blender
viewport. Empty IDs leave native modifier defaults in effect; use Clear selection
when the intent is to remove an incoming selection.

**Results.** Each node receives and passes on the full OVITO pipeline. Particle
properties, bonds, tables, surfaces, and other results remain available to later
modifiers and scripts. The current Particle Output converts particle positions
and supported numeric particle properties only. It does not yet draw OVITO bond,
surface, voxel, trajectory-line, or plot visualizations. Thus a Create bonds node
can feed Bond analysis, but it will not itself draw cylinders in Blender. A
Color coding node creates Color data; the Blender material must read that
attribute to display it. OVITO visual-element settings do not automatically
configure Blender materials or geometry. Table results can be accessed in a
following OVITO Script, for example:

```python
# After a Histogram node:
data = pipeline.compute(0)
print(data.tables["histogram[c_energy]"].xy())
```

Tests cover catalog/category completeness, serialization and setter roundtrips
for native parameters, save/reopen, and direct numerical comparisons with OVITO
for representative analysis, coloring, selection, structure-identification,
modification, and visualization modifiers. They also exercise secondary files,
configuration methods, Python functions, and manual selection. They do not
validate every scientific algorithm or every possible input dataset.

**Installed catalog (OVITO 3.13.1).**

**Analysis**

- Atomic strain (`AtomicStrainModifier`)
- Bond analysis (`BondAnalysisModifier`)
- Cluster analysis (`ClusterAnalysisModifier`)
- Coordination analysis (`CoordinationAnalysisModifier`)
- Dislocation analysis (DXA) (`DislocationAnalysisModifier`)
- Displacement vectors (`CalculateDisplacementsModifier`)
- Elastic strain calculation (`ElasticStrainModifier`)
- Grain segmentation (`GrainSegmentationModifier`)
- Histogram (`HistogramModifier`)
- Scatter plot (`ScatterPlotModifier`)
- Spatial binning (`SpatialBinningModifier`)
- Spatial correlation function (`SpatialCorrelationFunctionModifier`)
- Structure factor (`StructureFactorModifier`)
- Time averaging (`TimeAveragingModifier`)
- Time series (`TimeSeriesModifier`)
- Voronoi analysis (`VoronoiAnalysisModifier`)
- Wigner-Seitz defect analysis (`WignerSeitzAnalysisModifier`)

**Coloring**

- Ambient occlusion (`AmbientOcclusionModifier`)
- Assign color (`AssignColorModifier`)
- Color by type (`ColorByTypeModifier`)
- Color coding (`ColorCodingModifier`)

**Modification**

- Affine transformation (`AffineTransformationModifier`)
- Combine datasets (`CombineDatasetsModifier`)
- Compute property (`ComputePropertyModifier`)
- Delete selected (`DeleteSelectedModifier`)
- Freeze property (`FreezePropertyModifier`)
- Load trajectory (`LoadTrajectoryModifier`)
- Python script (`PythonModifier`)
- Replicate (`ReplicateModifier`)
- Slice (`SliceModifier`)
- Smooth trajectory (`SmoothTrajectoryModifier`)
- Unwrap trajectories (`UnwrapTrajectoriesModifier`)
- Wrap at periodic boundaries (`WrapPeriodicImagesModifier`)

**Selection**

- Clear selection (`ClearSelectionModifier`)
- Expand selection (`ExpandSelectionModifier`)
- Expression selection (`ExpressionSelectionModifier`)
- Invert selection (`InvertSelectionModifier`)
- Manual selection (`ManualSelectionModifier`)
- Select type (`SelectTypeModifier`)

**Structure identification**

- Ackland-Jones analysis (`AcklandJonesModifier`)
- Centrosymmetry parameter (`CentroSymmetryModifier`)
- Chill+ (`ChillPlusModifier`)
- Common neighbor analysis (`CommonNeighborAnalysisModifier`)
- Identify diamond structure (`IdentifyDiamondModifier`)
- Polyhedral template matching (`PolyhedralTemplateMatchingModifier`)
- VoroTop analysis (`VoroTopModifier`)

**Visualization**

- Construct surface mesh (`ConstructSurfaceModifier`)
- Coordination polyhedra (`CoordinationPolyhedraModifier`)
- Create bonds (`CreateBondsModifier`)
- Create isosurface (`CreateIsosurfaceModifier`)
- Generate trajectory lines (`GenerateTrajectoryLinesModifier`)

**Python-based modifiers**

- Identify fcc planar faults (`IdentifyFCCPlanarFaultsModifier`)
- Render LAMMPS regions (`RenderLAMMPSRegionsModifier`)
