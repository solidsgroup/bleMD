# BleMD - Advanced Visualization for Molecular Dynamics Simulations

![outputsmall](https://github.com/user-attachments/assets/000a9944-9ccb-445e-aa31-7881d3356ce0)

### Overview

**BleMD** enhances the visualization of molecular dynamics (MD) simulations by leveraging the analysis tools of OVITO and the advanced capabilities of Blender, a state-of-the-art 3D rendering and animation platform. This plugin empowers researchers to transform their simulation data into stunning, high-quality visualizations.

By integrating MD data with Blender, bleMD enables users to:

- Import simulation data seamlessly.
- Analyze data in  Blener using existing OVITO scripts
- Harness Blender's powerful rendering engines to produce eye-catching visualizations.
- Animate complex phenomena with precision and flexibility using precise interpolation and a robust animation system
- Customize visuals with dynamic, data-driven atom properties, including color, transparency, emissivity, and size.

Blender's rich toolset and intuitive interface make it an ideal platform for creating compelling visual representations of simulation data, offering unmatched control and creativity.

### Key Features

- **Dynamic Properties**: Control atom properties dynamically using Blender expressions or imported simulation data.
- **Familiarity**: Manipulate Blender systems through a simple, familiar interface which automatically configures Blender systems
- **Custom Shaders**: Apply advanced material settings using custom shaders tailored for MD data.
- **Automation**: Scripts for importing, processing, and visualizing simulation data with minimal manual effort.
- **Support for OVITO Modifiers**: Apply OVITO commands directly to imported pipelines.

---

### Installation

From this repository, run `make install` to build the ZIP, install bleMD, and
save its enabled state in your Blender preferences. Restart any already-open
Blender windows to load the update.
Before saving preferences, the installer backs up an existing `userpref.blend`
as `userpref.blemd-backup.blend` in the same configuration directory.
Installation is verified in a fresh Blender process. This avoids Blender 4.2's
unstable hot reload of generated node types; the current interactive window
must still be restarted after an update.

The default executable is `/opt/blender-4.2.2-linux-x64/blender`. Override it
with `make install BLENDER=/path/to/blender` if needed. OVITO must be available
in Blender's Python; the add-on installs it with pip on first enablement if
missing. Later enablements reuse the installed version.

For manual installation, run `make build`, then use Blender's
**Edit > Preferences > Add-ons > Install from Disk** to select `bleMD.zip` and
enable bleMD.

### Development loop (Blender 4.2.2)

Save your scene and close the previous Blender window, then run:

```bash
make dev
```

This builds `bleMD.zip`, runs the smoke test, installs the update in your normal
Blender profile, and opens Blender. If a test fails, installation and launch
stop. The terminal shows Blender output and stays attached until Blender exits.
To check changes against a saved scene:

```bash
make dev BLEND=/absolute/path/to/scene.blend
```

Individual steps are also available:

| Command | Action |
| --- | --- |
| `make build` | Rebuild `bleMD.zip`, excluding Python caches and deleted files |
| `make test` | Build and test using temporary Blender settings and add-on files |
| `make install` | Build, install/update, and save enablement in your normal profile |
| `make run` | Open Blender; accepts `BLEND=/path/to/scene.blend` |
| `make uninstall` | Remove bleMD and save the preference change |
| `make clean` | Remove the generated ZIP |

The smoke test uses the actual Blender executable and OVITO. It checks saved
enablement across processes, disable/enable cleanup, reinstallation, LAMMPS
import, particle ordering, geometry nodes, materials, and interpolation of
positions and scalar data, and uninstallation. It does not check rendered appearance. Temporary
settings and add-on files are removed afterward; OVITO uses Blender's existing
Python environment (and may be installed there if missing).
The node tests also cover script execution, graph errors, save/reopen, copied
trees, particle count changes, and interpolation with reordered particle IDs.

For a small manual check, use **Add > Open MD file** in the 3D View to open
`tests/fixtures/tiny.dump`, then click **Load File** in the object's
**bleMD Molecular Dynamics** panel. It contains three atoms and two frames.
Set the timeline to frame 0 or 1 and click **Load File** to view each frame.

The workflow can also run from any directory without Make:

```bash
python3 /path/to/bleMD/scripts/workflow.py dev --blend /path/to/scene.blend
```

---

### Usage

Analysis nodes can output scalar, vector, and tensor fields independently of the
particle data stream. For example, connect Atomic Strain → Color Map → Particle
Output / Color while File Source feeds Particle Output / Data directly. See the
[particle-field workflow](docs/particle-fields.md) for connections, shader and
Geometry Nodes attributes, compatibility, and an example trajectory.

The **bleMD node editor** is the main interface for new pipelines:

1. Choose **Window → bleMD Layout** for a workspace with three orthographic
   independently navigable views (Top, Front, Right), a perspective view, the bleMD editor below, and a
   timeline. Alternatively, change any area's **Editor Type** to **bleMD**.
2. Click **New Pipeline** in the header. This creates a connected
   **File Source / Atom ID → Color Map → Particle Output / Color** graph,
   with **File Source / Data** also connected directly to **Particle Output / Data**. If you clicked
   Blender's generic **New** button first, **New Pipeline** fills the empty tree.
3. Choose a simulation file on **File Source**. For a quick check, use
   `tests/fixtures/tiny.dump`. The source exposes Atom ID, Atom Type, Position,
   and the other numeric fields found in the file as typed output sockets.
4. The output updates automatically and creates its own mesh object without replacing
   the selected object. Use **Select Output**, then frame it in the 3D Viewport
   with Numpad `.`. The default Color Map fits the Atom ID range at simulation
   frame 0, keeping the color scale stable during playback. Updating again
   replaces that output's particle data.
5. Set radius and choose a material on **Particle Output**; edits update automatically.
   The default color connection creates a shader reading `bleMD Color`.
   Reconnect any scalar source field to Color Map to color by a different property.
   Its **Colorbar** selector includes all 111 existing presets. Radius accepts an
   optional scalar field and scale. Unconnected Radius, Color, Value, Vector,
   and added shader fields have editable defaults directly on their input sockets.
   Linking a field overrides its default; disconnecting restores the saved value.
   Use **+ Value / + Vector / + Color** on Particle Output to export named fields
   for shader **Attribute** nodes. In the Shader Editor, **Add → bleMD Color Map**
   adds the same palettes; select it and choose **N → bleMD → Colorbar**.
   The particle geometry uses round viewport spheres and render-time points;
   use **Cycles** for rendering these points. **Adaptive spheres** lowers preview
   tessellation above 5,000 atoms to reduce memory without omitting particles.
   bleMD selects **Cycles** at startup; you can choose another renderer afterward.
   Viewport and camera far clipping expand automatically for large MD coordinates
   and distant views, without moving the camera or synchronizing the quad views.

Use **Add → Particle Fields → CPK Color** to color by chemical element. Connect
**File Source / Atom Type → CPK Color / Element → Particle Output / Color**.
Element names are read automatically; for numeric types, enter a mapping such
as `1=C, 2=O`. An explicit **Atomic numbers** mode and an editable **Unmapped**
color are also available. See [CPK element coloring](docs/particle-fields.md#cpk-element-coloring).

Use **Add → Utilities** for **Math** (41 operations, including Add and Multiply),
**Vector Math** (27 operations), **Map Range**, **Clamp**, **Mix**, constant
**Value / Vector / RGB**, and **Separate / Combine XYZ or Color**. For example,
connect `c_energy → Math (Multiply, 2) → Radius`, or send the result through
Color Map. Unconnected inputs are editable constants. Results can also feed
named Particle Output fields for shaders and Geometry Nodes. **Add → Layout**
provides Blender's native Frame and Reroute nodes. These utilities evaluate
particle fields in bleMD; Blender's other shader and geometry nodes remain in
their respective editors.

The starter graph contains no script node. Add an **OVITO Script** manually
from **Add → Input / Output / Scripts** when needed. **New Script** creates a
Blender text and enables the node. Edit the text in Blender's Text Editor, for
example:

```python
from ovito.modifiers import CentroSymmetryModifier
pipeline.modifiers.append(CentroSymmetryModifier(num_neighbors=12))
```

The script receives `pipeline` and configures its modifiers, just like the
previous processing-script interface. It runs when the recipe changes or on manual **Update**, before
sampling trajectory frames. Scrubbing reuses the compiled pipeline. Multiple Script nodes can be chained. Disabling
one passes its input pipeline through unchanged. Scripts are ordinary Python
executed inside Blender.

All concrete modifiers exposed by the installed OVITO Python package are also
available as individual nodes under **Add** (Shift+A), in OVITO's own categories:
**Analysis, Coloring, Modification, Selection, Structure identification,
Visualization**, and **Python-based modifiers**. With OVITO 3.13.1 this is **53
modifier types**. Connect them between File Source and Particle Output; scripts
and modifier nodes can be freely mixed in the same chain.

Editing a parameter checks its override box automatically. Uncheck it to let
OVITO initialize its own default. Nested settings are available in the selected
node's sidebar. Reference/source files have file pickers; complex settings and
methods are available through each node's **New Configuration** text, which
receives `modifier` and `pipeline`. See the [modifier guide](docs/modifiers.md)
for the full catalog, examples, and current output limitations.

Set playback timing directly on **File Source**:

- **Start Frame** defaults to **0** and places the first saved MD frame on the
  Blender timeline.
- **Timesteps per Frame** defaults to **1**. A value of **5** places consecutive
  saved MD frames five Blender frames apart, with four interpolated frames
  between them. Values above one automatically enable smooth interpolation.
  Positions and floating-point fields interpolate by particle ID; integer IDs,
  types, and selections retain the preceding saved frame's values. Interpolation
  requires unique IDs and matching particle membership between adjacent frames.
  For changing membership, use **1** to display only saved frames.
- Drag the timeline or press Play to animate the particles. Frames outside the
  trajectory clamp to its endpoints. Animation rendering uses the same mapping.
- The first successful evaluation and subsequent source timing edits fit the
  scene range to the trajectory. **N → bleMD → Fit Timeline** reapplies it manually.
  Saved pipelines migrate their previous timing settings to File Source.
- **Automatic Updates** is on by default. Turn it off in **N → bleMD** for
  large datasets: file discovery, recipe edits, and timeline changes then wait
  for **Update**. **Refresh Fields** can still explicitly read the source schema.
  Turning automatic updates back on evaluates the current frame and recipe.
- Node, link, and Text edits are detected within roughly 0.15 seconds; computation
  time depends on the dataset and modifiers. Evaluation runs on Blender's main
  thread. Playback speed is limited by evaluation and viewport geometry cost.
  bleMD enables **Render → Lock Interface** for its scene to keep mesh changes
  safe during animation rendering.

**Attributes** accepts comma-separated OVITO property names. Leave it empty to
transfer all supported numeric properties: scalars and three-component vectors.
Other vector/tensor sizes are skipped when importing all properties; explicitly
requesting an unsupported property reports an error. Integer properties must
fit Blender's 32-bit attribute range. All original OVITO data remains available
to scripts before the final Blender conversion.

Each tree currently requires **one Particle Output**. Use separate trees for
separate objects. Each recipe is associated with a scene for playback. Recipes,
script references, playback settings, and output references save in the `.blend`
file, including the bleMD workspace. Script edits update automatically. **Update**
forces a fresh OVITO pipeline, including rereading source files changed on disk.
External file changes are not watched automatically. Failed graph/script validation
keeps the previous output. Copied trees create separate output objects.

Existing scenes using the Object-properties interface continue to work. That
panel is hidden for node-owned outputs; manage those through their node tree.

### Legacy object workflow

1. **Load Simulation Data**:
   - Use the **Load Data File** button to import MD simulation files (e.g., LAMMPS dump files).
   - Alternatively, load using custom OVITO I/O scripts.

2. **Customize Shading and Rendering**:
   - Assign materials to objects.
   - Control atom radius, color, and shading via properties panel.

3. **Animate Frames**:
   - Set keyframes based on MD data for dynamic visualizations.

4. **Render Outputs**:
   - Set output paths for renders and animations.
   - Export high-resolution images or videos.

---

### Example Workflow

#### Step 1: Load a LAMMPS Dump File
- Navigate to the **Properties Panel > bleMD Molecular Dynamics** section.
- Specify the file path and load the file.

#### Step 2: Apply OVITO Modifiers
- Enable custom OVITO scripts to preprocess the simulation data.

#### Step 3: Customize Materials
- Create materials with dynamic properties (e.g., color mapping based on simulation data).

#### Step 4: Animate and Render
- Set the animation frame stride, rig keyframes, and render the sequence.

### Gallery
![indent1 NEW  (2)](https://github.com/user-attachments/assets/13f859b0-1195-47d5-9bc2-20eb59ec6857)
![0650](https://github.com/user-attachments/assets/856f8ade-d7dd-4cf2-a50c-c6556b99874d)
![0036](https://github.com/user-attachments/assets/60996955-14bc-4555-9345-0faa347cd951)
![glasspink](https://github.com/user-attachments/assets/b0948ef8-9b46-49de-8ec3-f0a4a2f0b765)
![viridisexample](https://github.com/user-attachments/assets/1b4336bc-de1c-460c-a50b-c93ac5dbe60a)
![output-onlinepngtools](https://github.com/user-attachments/assets/41ab5d47-b604-4b34-b9cb-b65b5d3c00b2)
