from flask import request
import logging
import dash
from dash import dcc
from dash import html
import dash_leaflet as dl
from dash.dependencies import Input, Output
import os
import time
import socket

class LeafletMap():
    def __init__(self):
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        MAP_ID = "map"
        DRONE_ID = "drone-location"
        OTHER_DRONES_LAYER_ID = "other-drones-layer"
        CIRCLES_LAYER_ID = "circles-layer"
        PATH_LAYER_ID = "path-layer"
        QR_CODE_ID = "qr-code-marker"
        
        # Create assets directory if it doesn't exist
        self.setup_assets_directory()
        
        self.coordsOfPath = []
        self.altOfPathCoords = []
        self.mapCenter = [-35.3629228, 149.1650756]
        self.drone_location = [-35.3629228, 149.1650756]
        self.other_drone_locations = [
            [-35.3618486, 149.1625713],
            [-35.3636389, 149.1675149],
        ]
        self.circles = [
            {"location": [-35.3597765, 149.1631441], "radius": 70},
            {"location": [-35.3587919, 149.1662285], "radius": 50},
        ]
        self.path = []
        self.qr_code_location = [-35.36236418471588, 149.1652373]
        
        # Initialize Dash app
        self.app = dash.Dash(__name__, 
                             prevent_initial_callbacks=True,
                             assets_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets'))
        
        # Use the correct icon filenames based on what's in the icons directory
        # The asset URLs should be relative to the assets folder
        self.droneIcon = {
            "iconUrl": "/assets/plane.png",  # Will look in assets/plane.png
            "iconSize": [30, 30],
        }
        
        self.otherDroneIcon = {
            "iconUrl": "/assets/plane1.png",  # Will look in assets/plane1.png
            "iconSize": [30, 30],
        }

        self.pathIcon = {
            "iconUrl": "/assets/nokta1.png",  # Will look in assets/nokta1.png
            "iconSize": [10, 10],
        }

        self.qr_code_icon = {
            "iconUrl": "/assets/nokta.png",  # Will look in assets/nokta.png
            "iconSize": [50, 50],
        }
        
        self.drone_direction = 0
        self.pixel_location = [0, 0]
        self.detect_location = [0, 0]
        self.detects = []
        self.goDrone = False
        self.goTarget = False
        self.count = 0
        self.followBtnType = "drone"
        self.targetFollow = False
        self.server_running = False
        self.server_port = None

        # Create app layout
        self.app.layout = html.Div([
            dl.Map(style={'width': '100%', 'height': '93vh', 'margin': "auto", "display": "block",'color': '#7FDBFF'},
                zoom=20, id=MAP_ID, center=self.mapCenter,
                zoomControl=False,
                children=[
                    dl.TileLayer(url="http://www.google.cn/maps/vt?lyrs=s@189&gl=cn&x={x}&y={y}&z={z}"),
                    html.Div(id="MilitaryGridTile", style={'outline': '1px solid green', 'fontWeight': 'bold', 'fontSize': '14pt'}),
                    dl.LayerGroup(id=OTHER_DRONES_LAYER_ID),
                    dl.LayerGroup(id=CIRCLES_LAYER_ID),
                    dl.LayerGroup(id=PATH_LAYER_ID),
                    dl.LayerGroup(id=QR_CODE_ID),
                    dcc.Interval(
                        id='interval-component',
                        interval=1*500,
                        n_intervals=0
                    ),
                    dl.Marker(id=DRONE_ID, position=self.drone_location, n_clicks=0, icon=self.droneIcon),
                ]
            ),
            html.Button("Drona Git", id="btn", style={'position': 'absolute', 'top': '10px', 'left': '10px', 'zIndex': '1000'}),
            # Add a health check route
            html.Div(id="server-status", style={"display": "none"})
        ], style={'position': 'relative'})
        
        # Add a callback for health check
        @self.app.callback(
            Output("server-status", "children"),
            Input('interval-component', 'n_intervals')
        )
        def update_health_check(n):
            return "OK"
            
        print("Harita oluşturuldu. İkonları kontrol edin: assets/ dizininde plane.png, plane1.png, nokta1.png, nokta.png olmalıdır.")

        # Define callbacks
        @self.app.callback(
            Output(DRONE_ID, "position"),
            Output(DRONE_ID, "iconAngle"),
            Input('interval-component', 'n_intervals')
        )
        def update_drone_location(n):
            return self.drone_location, self.drone_direction

        @self.app.callback(Output(OTHER_DRONES_LAYER_ID, "children"), Input('interval-component', 'n_intervals'))
        def update_other_drone_locations(n):
            return [
                dl.Marker(position=loc, icon=self.otherDroneIcon) for loc in self.other_drone_locations
            ]

        @self.app.callback(Output(CIRCLES_LAYER_ID, "children"), Input('interval-component', 'n_intervals'))
        def update_circles(n):
            return [
                dl.Circle(center=circle['location'], radius=circle['radius'], color='red', fillColor='red', fillOpacity=0.5, stroke=True)
                for circle in self.circles
            ]

        @self.app.callback(Output(PATH_LAYER_ID, "children"), Input('interval-component', 'n_intervals'))
        def update_path(n):
            path_markers = [dl.Marker(position=loc, icon=self.pathIcon) for loc in self.path]
            if self.path:
                return path_markers
            return []

        @self.app.callback(Output(QR_CODE_ID, "children"), Input('interval-component', 'n_intervals'))
        def update_qr_code(n):
            return [
                dl.Marker(position=self.qr_code_location, icon=self.qr_code_icon)
            ]

        @self.app.callback(Output(MAP_ID, "center"), Input("btn", "n_clicks"))
        def center_map_on_drone(n_clicks):
            return self.drone_location

    def setup_assets_directory(self):
        """Create assets directory and ensure icons are available"""
        # Create assets directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(base_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        
        print(f"Assets directory: {assets_dir}")
        
        # Check if icons exist
        icon_files = ['plane.png', 'plane1.png', 'nokta.png', 'nokta1.png']
        for icon in icon_files:
            icon_path = os.path.join(assets_dir, icon)
            if not os.path.exists(icon_path):
                print(f"Uyarı: {icon} dosyası bulunamadı. Lütfen {assets_dir} dizinine kopyalayın.")
                
                # Try to find icons in an "icons" directory and copy them
                icons_dir = os.path.join(base_dir, 'icons')
                if os.path.exists(os.path.join(icons_dir, icon)):
                    import shutil
                    try:
                        shutil.copy(os.path.join(icons_dir, icon), icon_path)
                        print(f"{icon} dosyası {icons_dir} dizininden kopyalandı.")
                    except Exception as e:
                        print(f"Dosya kopyalama hatası: {e}")
        
        # Also check for CSS file
        css_file = os.path.join(assets_dir, 'style.css')
        if not os.path.exists(css_file):
            with open(css_file, 'w') as f:
                f.write("""
                body {
                    margin: 0;
                    padding: 0;
                }
                .leaflet-container {
                    height: 100vh;
                    width: 100%;
                    max-width: 100%;
                    max-height: 100%;
                }
                """)
            print(f"CSS dosyası oluşturuldu: {css_file}")

    def shutdown_server(self):
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Werkzeug sunucusu doğru yanıt vermedi.')
        func()
        self.server_running = False
    
    def shutdown(self):
        try:
            self.shutdown_server()
            return 'Harita sunucusu kapatıldı...'
        except Exception as e:
            print(f"Harita sunucusu kapatılırken hata: {e}")
            return f'Harita sunucusu kapatılamadı: {e}'

    def droneCoord(self, lat, lon, yaw):
        try:
            self.drone_location = [float(lat), float(lon)]
            self.drone_direction = float(yaw)  # Also update direction
        except Exception as e:
            print(f"Dron koordinatları alınamadı: {e}") 
        return 'OK'

    def update_other_drone_coords(self, new_coords):
        try:
            self.other_drone_locations = new_coords
        except Exception as e:
            print(f"Diğer dron koordinatları alınamadı: {e}") 
        return 'OK'

    def update_circle_coords(self, new_circles):
        try:
            self.circles = new_circles
        except Exception as e:
            print(f"Daire koordinatları alınamadı: {e}") 
        return 'OK'

    def add_path(self, new_path):
        try:
            self.path = new_path
        except Exception as e:
            print(f"Yeni yol koordinatları eklenemedi: {e}") 
        return 'OK'

    def find_available_port(self, start_port=8150, max_attempts=10):
        """Find an available port starting from start_port"""
        port = start_port
        for _ in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except socket.error:
                port += 1
        raise RuntimeError(f"Kullanılabilir bir port bulunamadı ({start_port}-{start_port+max_attempts-1} aralığında).")

    def start_map(self, port_no=8150):
        """Start the map server on the specified port or find an available port"""
        try:
            if self.server_running:
                print(f"Harita sunucusu zaten çalışıyor - Port: {self.server_port}")
                return
                
            # Try to use specified port, or find an available one
            try:
                available_port = self.find_available_port(start_port=port_no)
            except RuntimeError as e:
                print(f"Port hatası: {e}")
                available_port = self.find_available_port(start_port=8100)
                
            print(f"Harita başlatılıyor - Port: {available_port}")
            self.server_port = available_port
            self.server_running = True
            
            # Set up a handler for potential errors
            try:
                # Use app.run instead of app.run_server
                self.app.run(debug=False, port=available_port, host='0.0.0.0')
            except Exception as e:
                print(f"Harita sunucusu çalışırken hata: {e}")
                self.server_running = False
        except Exception as e:
            print(f"Harita sunucusu başlatma hatası: {e}")
            self.server_running = False
            raise
            
    def is_server_ready(self, port=None):
        """Check if server is ready to accept connections"""
        if port is None:
            port = self.server_port or 8150
            
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                if result == 0:
                    # Try to fetch server status
                    import urllib.request
                    try:
                        with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as response:
                            return response.getcode() == 200
                    except:
                        pass
                return False
        except Exception:
            return False

    def get_map_url(self):
        """Return the URL for the map"""
        port = self.server_port or 8150
        return f"http://localhost:{port}/"