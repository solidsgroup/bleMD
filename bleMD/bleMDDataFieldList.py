import bpy
from bpy.types import (PropertyGroup,UIList)
from bpy.props import (StringProperty,BoolProperty)


class bleMDDataFieldsLIProperty(PropertyGroup):
    """Group of properties representing an item in the list."""

    name: StringProperty(
        name="Name",
        description="Property",
        default="Untitled")

    enable: BoolProperty(
        name="Enable",
        description="Include as a coloring property")

    editable: BoolProperty(
        name="Editable",
        description="Whether or not the user can modify",
        default=True,
    )


class bleMDDataFieldsList(UIList):
    """Demo UIList."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        # We could write some code to decide which icon to use here...
        custom_icon = 'OBJECT_DATAMODE'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.label(text=item.name, icon=custom_icon)
            row = layout.row()
            row.enabled = item.editable
            row.prop(item, "enable")

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon=custom_icon)


