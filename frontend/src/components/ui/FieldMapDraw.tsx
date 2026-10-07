"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Navigation, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

interface Props {
  center: [number, number];
  onPolygonChange: (geojson: GeoJSON.Polygon | null, areaHectares: number) => void;
  onLocationDetected?: (details: { locationStr: string; lat: number; lng: number }) => void;
}

export default function FieldMapDraw({ center, onPolygonChange, onLocationDetected }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const drawnItemsRef = useRef<any>(null);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  // Auto detect user live GPS location on mount
  const locateUser = () => {
    if (!navigator.geolocation) return;
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setIsLocating(false);

        if (mapRef.current) {
          mapRef.current.setView([lat, lng], 17);
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const L = (window as any).L;
          if (L) {
            if (markerRef.current) {
              markerRef.current.setLatLng([lat, lng]);
            } else {
              markerRef.current = L.marker([lat, lng])
                .addTo(mapRef.current)
                .bindPopup("📍 <b>Your Current GPS Location</b><br/>Field boundary center reference point");
            }
            markerRef.current.openPopup();
          }
        }

        // Reverse geocode address using Nominatim API
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`
          );
          if (res.ok) {
            const data = await res.json();
            const addr = data.address || {};
            const locationStr =
              data.display_name ||
              `${addr.suburb || addr.village || addr.town || addr.city || ''}, ${addr.state || ''}`.trim();
            if (onLocationDetected) {
              onLocationDetected({ locationStr, lat, lng });
            }
          }
        } catch (e) {
          console.error("Reverse geocode failed:", e);
        }
      },
      async (err) => {
        console.warn("Browser Geolocation failed or low accuracy, attempting IP location fallback:", err);
        // Fallback to IP Geolocation API if browser GPS fails or is disabled
        try {
          const res = await fetch("https://ipapi.co/json/");
          if (res.ok) {
            const data = await res.json();
            if (data.latitude && data.longitude) {
              const lat = data.latitude;
              const lng = data.longitude;
              const locationStr = `${data.city || ''}, ${data.region || ''}, ${data.country_name || ''}`.trim();
              if (mapRef.current) {
                mapRef.current.setView([lat, lng], 15);
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const L = (window as any).L;
                if (L) {
                  if (markerRef.current) {
                    markerRef.current.setLatLng([lat, lng]);
                  } else {
                    markerRef.current = L.marker([lat, lng])
                      .addTo(mapRef.current)
                      .bindPopup(`📍 <b>Approximate Network Location (${data.city})</b>`);
                  }
                  markerRef.current.openPopup();
                }
              }
              if (onLocationDetected) {
                onLocationDetected({ locationStr, lat, lng });
              }
            }
          }
        } catch (ipErr) {
          console.error("IP Location fallback failed:", ipErr);
        } finally {
          setIsLocating(false);
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  // Search location using OpenStreetMap Nominatim
  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}`
      );
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          const lat = parseFloat(data[0].lat);
          const lng = parseFloat(data[0].lon);
          if (mapRef.current) {
            mapRef.current.setView([lat, lng], 16);
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const L = (window as any).L;
            if (L) {
              L.marker([lat, lng])
                .addTo(mapRef.current)
                .bindPopup(`📍 <b>${data[0].display_name}</b>`)
                .openPopup();
            }
          }
          if (onLocationDetected) {
            onLocationDetected({ locationStr: data[0].display_name, lat, lng });
          }
        }
      }
    } catch (err) {
      console.error("Location search failed:", err);
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    async function loadLeaflet() {
      if (typeof window === "undefined") return;
      if (mapRef.current) return;

      const L = (await import("leaflet")).default;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).L = L;
      await import("leaflet-draw");

      if (!isMounted || !containerRef.current || mapRef.current) return;

      // Fix icon paths
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
        iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
      });

      const map = L.map(containerRef.current, {
        center: center,
        zoom: 16,
      });

      // 1. Satellite Base Layer (Esri World Imagery)
      const esriSat = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
          attribution: "Tiles © Esri",
          maxZoom: 19,
        }
      );

      // 2. OpenStreetMap Standard (Clean vector map view)
      const osmMap = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          attribution: "&copy; OpenStreetMap contributors",
          maxZoom: 19,
        }
      );

      // 3. Google Satellite / Hybrid view
      const googleSat = L.tileLayer(
        "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        {
          attribution: "&copy; Google Maps",
          maxZoom: 20,
        }
      );

      // Add default base layer
      googleSat.addTo(map);

      // Add layer control selector (bottom-right to avoid overlapping search/location bar)
      const baseMaps = {
        "Google Satellite Hybrid": googleSat,
        "OpenStreetMap Standard": osmMap,
        "Esri Satellite": esriSat,
      };
      L.control.layers(baseMaps, undefined, { position: "bottomright" }).addTo(map);

      // FeatureGroup to store drawn items
      const drawnItems = new L.FeatureGroup();
      drawnItems.addTo(map);
      drawnItemsRef.current = drawnItems;

      // Leaflet Draw Control with Enhanced Styling
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const drawControl = new (L.Control as any).Draw({
        edit: {
          featureGroup: drawnItems,
          remove: true,
        },
        draw: {
          polygon: {
            allowIntersection: false,
            showArea: true,
            shapeOptions: {
              color: "#10b981",
              fillColor: "#059669",
              fillOpacity: 0.35,
              weight: 3,
              dashArray: "4, 6",
            },
          },
          rectangle: {
            shapeOptions: {
              color: "#10b981",
              fillColor: "#059669",
              fillOpacity: 0.35,
              weight: 3,
            },
          },
          circle: false,
          circlemarker: false,
          marker: false,
          polyline: false,
        },
      });
      map.addControl(drawControl);

      // Calculate polygon area in hectares
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const calcArea = (layer: any) => {
        const latlngs = layer.getLatLngs()[0];
        if (!latlngs) return 0;
        const R = 6371000;
        let area = 0;
        const n = latlngs.length;
        for (let i = 0; i < n; i++) {
          const j = (i + 1) % n;
          const lat1 = (latlngs[i].lat * Math.PI) / 180;
          const lat2 = (latlngs[j].lat * Math.PI) / 180;
          const dLng = ((latlngs[j].lng - latlngs[i].lng) * Math.PI) / 180;
          area += (lat2 - lat1) * dLng;
        }
        area = Math.abs(area) * R * R * 0.5;
        return Math.max(0.01, parseFloat((area / 10000).toFixed(4)));
      };

      // Extract GeoJSON Polygon object
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const toGeoJSON = (layer: any): GeoJSON.Polygon => {
        const latlngs = layer.getLatLngs()[0];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const ring = latlngs.map((pt: any) => [
          parseFloat(pt.lng.toFixed(6)),
          parseFloat(pt.lat.toFixed(6)),
        ]);
        ring.push(ring[0]);
        return { type: "Polygon", coordinates: [ring] };
      };

      // Attach Interactive Acreage Tooltip & Centroid Popup to Layer
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const bindPolygonTooltip = (layer: any, hectares: number) => {
        const center = layer.getBounds().getCenter();
        const popupContent = `
          <div style="text-align: center; font-family: monospace; padding: 2px;">
            <b style="color: #10b981; font-size: 13px;">🌾 Verified Crop Plot</b><br/>
            <span>Area: <b>${hectares} Hectares</b> (~${(hectares * 2.47105).toFixed(2)} Acres)</span><br/>
            <span style="font-size: 10px; color: #64748b;">Center: ${center.lat.toFixed(5)}, ${center.lng.toFixed(5)}</span>
          </div>
        `;
        layer.bindTooltip(`🌾 ${hectares} Ha (${(hectares * 2.47105).toFixed(1)} Acres)`, {
          permanent: true,
          direction: "center",
          className: "polygon-area-tooltip",
        }).bindPopup(popupContent);
      };

      // Events
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      map.on((L as any).Draw.Event.CREATED, (e: any) => {
        drawnItems.clearLayers();
        const layer = e.layer;
        drawnItems.addLayer(layer);
        const ha = calcArea(layer);
        const geojson = toGeoJSON(layer);
        bindPolygonTooltip(layer, ha);
        onPolygonChange(geojson, ha);
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      map.on((L as any).Draw.Event.EDITED, () => {
        const layers = drawnItems.getLayers();
        if (layers.length === 0) {
          onPolygonChange(null, 0);
          return;
        }
        const layer = layers[0];
        const ha = calcArea(layer);
        bindPolygonTooltip(layer, ha);
        onPolygonChange(toGeoJSON(layer), ha);
      });

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      map.on((L as any).Draw.Event.DELETED, () => {
        onPolygonChange(null, 0);
      });

      mapRef.current = map;
      setMapLoaded(true);

      // Auto detect location on load
      locateUser();

      setTimeout(() => {
        map.invalidateSize();
      }, 300);
    }

    loadLeaflet();

    return () => {
      isMounted = false;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Store marker instance so we can move it
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markerRef = useRef<any>(null);

  useEffect(() => {
    // Set map view when latitude/longitude coordinates change
    if (mapRef.current && center[0] && center[1]) {
      mapRef.current.setView(center, 17);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const L = (window as any).L;
      if (L) {
        if (markerRef.current) {
          markerRef.current.setLatLng(center);
        } else {
          markerRef.current = L.marker(center)
            .addTo(mapRef.current)
            .bindPopup("📍 <b>Pranveer Singh Institute of Technology (PSIT), Kanpur</b>");
        }
        markerRef.current.openPopup();
      }
    }
  }, [center]);

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-emerald-800/60 bg-slate-900">
      {/* Load Leaflet & Leaflet-Draw styles */}
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      />
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"
      />

      <style jsx global>{`
        .polygon-area-tooltip {
          background-color: rgba(6, 78, 59, 0.9) !important;
          border: 1px solid #10b981 !important;
          color: #ffffff !important;
          font-weight: 700 !important;
          font-size: 11px !important;
          border-radius: 6px !important;
          padding: 2px 8px !important;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
        }
        .polygon-area-tooltip::before {
          border-top-color: rgba(6, 78, 59, 0.9) !important;
        }
      `}</style>

      {/* Map Control Bar (Search & Current Location Button) */}
      <div className="absolute top-2 left-12 right-4 z-[500] flex items-center justify-between gap-3 pointer-events-auto">
        <div className="flex-1 max-w-xs sm:max-w-sm flex items-center gap-1 bg-slate-950/85 backdrop-blur-md p-1 rounded-lg border border-slate-800 shadow-lg">
          <Input
            type="text"
            placeholder="Search village, city, or district..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSearch();
              }
            }}
            className="h-7 text-xs bg-transparent border-0 focus-visible:ring-0 text-white placeholder:text-slate-400"
          />
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={isSearching}
            onClick={() => handleSearch()}
            className="h-7 px-2 text-emerald-400 hover:bg-emerald-950/50"
          >
            {isSearching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
          </Button>
        </div>

        <Button
          type="button"
          size="sm"
          onClick={locateUser}
          disabled={isLocating}
          className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-8 px-3 shadow-lg flex items-center gap-1.5 shrink-0 z-[501]"
        >
          {isLocating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Navigation className="h-3.5 w-3.5" />}
          <span>{isLocating ? "Locating..." : "My Live Location"}</span>
        </Button>
      </div>

      {!mapLoaded && (
        <div className="h-[400px] w-full flex items-center justify-center text-slate-400 gap-2">
          <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
          <span className="text-xs">Detecting Your Exact GPS Location…</span>
        </div>
      )}

      <div
        ref={containerRef}
        className="w-full h-[400px] z-10"
        style={{ minHeight: "400px" }}
      />
    </div>
  );
}
