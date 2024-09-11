from pydm.widgets.qtplugin_base import WidgetCategory, qtplugin_factory
from pydm.widgets.qtplugin_extensions import RulesExtension

from cavity_widget import CavityWidget

# plugin
print("Loading custom PyDMDrawingPolyon with text!")
PyDMDrawingPolygonText = qtplugin_factory(
    CavityWidget,
    group=WidgetCategory.DISPLAY,
    is_container=True,
    extensions=[RulesExtension],
)
