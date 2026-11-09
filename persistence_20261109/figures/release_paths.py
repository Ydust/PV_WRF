from pathlib import Path
import sys

repository = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repository / "code"))
from audit_panel_alignment import require_matplotlib_panel_alignment

MAP = repository / "input/maps/shapefiles/natural_earth/cultural/ne_50m_admin_0_countries.shp"
