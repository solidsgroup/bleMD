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

1. **Clone this repository:**
   ```bash
   git clone https://github.com/your-repo/bleMD.git
   ```
2. **Install the plugin in Blender:**
   - Open Blender.
   - Go to `Edit > Preferences > Add-ons`.
   - Click `Install...` and select the `bleMD` folder.
   - Enable the plugin from the add-ons menu.
3. **Restart your computer**

---

### Usage

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
