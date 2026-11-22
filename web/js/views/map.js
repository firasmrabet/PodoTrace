/* ═══════════════════════════════════════════════════════════════════════
   map.js — centres de soin et urgences (OpenStreetMap réel avec Leaflet)
   ═══════════════════════════════════════════════════════════════════════ */
import { S, api, icon, h, num, toast, el, els } from '../core.js';

const TUNIS = { lat: 36.8065, lon: 10.1815 };
const CAT_COLORS = {
  emergency: '#C0392B',
  hospital: '#2980B9',
  wound_care: '#27AE60',
  clinic: '#16A085',
  podiatrist: '#D4AC0D',
  diabetologist: '#8E44AD',
  pharmacy: '#E67E22',
  other: '#7F8C8D',
};

export default async function map(root) {
  let coords = { ...TUNIS, source: 'default' };
  let category = 'all';
  let places = [];
  let selected = null;
  let origin = { ...TUNIS };
  let leafletMap = null;
  let markersLayer = null;
  let currentMapMode = 'satellite';
  let satelliteLayer = null;
  let satelliteLabelsLayer = null;
  let streetLayer = null;

  root.innerHTML = `
  <div class="page">
    <div class="masthead">
      <div>
        <div class="date">Référentiel de soins & urgences</div>
        <h1>Centres et urgences</h1>
        <div class="sub" id="geo-sub">Détection de votre position en cours…</div>
      </div>
      <div class="right">
        <button class="btn ghost sm" id="locate">${icon('map', 14)} Actualiser ma position</button>
      </div>
    </div>

    <div class="wrap-gap" id="cats" style="margin-bottom:14px">
      ${[['all', 'Tous'], ['emergency', 'Urgences 24/7'], ['wound_care', 'Plaies & cicatrisation'],
        ['hospital', 'Hôpitaux'], ['podiatrist', 'Podologues'], ['diabetologist', 'Diabétologues'], ['pharmacy', 'Pharmacies']]
        .map(([k, l]) => `<button class="pill ${k === 'all' ? 'info' : 'outline'}" data-cat="${k}"
          style="padding:7px 13px; font-size:11.5px; cursor:pointer">${l}</button>`).join('')}
    </div>

    <div class="split">
      <div>
        <div class="map-frame" id="frame" style="position:relative; width:100%; height:480px; min-height:480px; border-radius:12px; overflow:hidden; background:#0f172a; border:1px solid var(--border)">
          <div id="leaflet-map" style="position:absolute; inset:0; width:100%; height:100%; z-index:1"></div>
          <canvas id="canvas" width="900" height="620" style="display:none; position:absolute; inset:0; width:100%; height:100%"></canvas>
          <div id="pins" style="position:absolute; inset:0; pointer-events:none; z-index:2"></div>
          <!-- Sélecteur de vue : Satellite HD vs Plan des rues -->
          <div id="layer-switcher" style="position:absolute; top:12px; right:12px; z-index:1000; background:rgba(255,255,255,0.95); backdrop-filter:blur(6px); border-radius:8px; padding:3px; box-shadow:0 2px 10px rgba(0,0,0,0.25); display:flex; gap:3px">
            <button id="btn-satellite" class="btn sm" style="padding:5px 12px; font-size:11.5px; border-radius:6px; font-weight:600; cursor:pointer; background:#0f766e; color:#fff; border:none; transition:all 0.2s">🛰️ Satellite réel</button>
            <button id="btn-streets" class="btn ghost sm" style="padding:5px 12px; font-size:11.5px; border-radius:6px; font-weight:600; cursor:pointer; background:transparent; color:#334155; border:none; transition:all 0.2s">🗺️ Plan des rues</button>
          </div>
        </div>
        <div class="row between mt-sm">
          <span class="tiny" id="source-label">Source : Imagerie satellite HD / Référentiel médical national</span>
          <span class="tiny">Rayon 25 km · Données géographiques en direct</span>
        </div>
        <div class="tiny" style="margin-top:6px; line-height:1.5; color:var(--ink-3)">
          Carte satellite interactive en direct. En cas d'urgence vitale, contactez sans délai le <b>15</b> (SAMU) ou le <b>190</b> (Tunisie).
        </div>
      </div>

      <div>
        <div class="card" id="detail" style="display:none"></div>
        <div class="card" style="margin-top:0">
          <div class="card-h"><div class="t">Résultats</div><span class="tiny" id="count">—</span></div>
          <div id="list" style="display:grid; gap:0; max-height:450px; overflow-y:auto">
            <div class="loading-page" style="min-height:120px"><div class="spinner dark"></div></div>
          </div>
        </div>
      </div>
    </div>
  </div>`;

  const frame = el('#frame', root);
  const pinsHost = el('#pins', root);
  const isCurrentView = () => root.contains(frame);

  els('[data-cat]', root).forEach((b) =>
    b.addEventListener('click', () => {
      category = b.dataset.cat;
      els('[data-cat]', root).forEach((x) => {
        x.className = `pill ${x.dataset.cat === category ? 'info' : 'outline'}`;
        x.style.padding = '7px 13px'; x.style.fontSize = '11.5px'; x.style.cursor = 'pointer';
      });
      load();
    }));

  el('#locate', root).addEventListener('click', () => {
    coords = { lat: -999, lon: -999 };
    locate(true);
  });

  async function locate(userTriggered = false, silent = false) {
    if (!isCurrentView()) return;
    const sub = el('#geo-sub', root);
    if (!sub) return;
    if (!navigator.geolocation) {
      sub.textContent = 'Géolocalisation indisponible — position par défaut : Tunisie.';
      return;
    }
    if (!silent) sub.textContent = 'Localisation GPS en cours…';
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          if (!isCurrentView()) {
            resolve(null);
            return;
          }
          const next = { lat: pos.coords.latitude, lon: pos.coords.longitude };
          const moved = Math.abs(next.lat - coords.lat) > 0.005 || Math.abs(next.lon - coords.lon) > 0.005;
          coords = { ...next, source: 'gps' };
          sub.innerHTML = `Position détectée · <b>${num(coords.lat, 4)}, ${num(coords.lon, 4)}</b> · rayon 25 km`;
          resolve(moved ? load() : null);
        },
        () => {
          if (!isCurrentView()) {
            resolve(null);
            return;
          }
          sub.textContent = userTriggered
            ? 'Accès refusé — recherche autour de la position actuelle.'
            : 'Position approximative (autorisez la géolocalisation pour cibler vos centres proches).';
          resolve(null);
        },
        { timeout: 7000, maximumAge: 60000, enableHighAccuracy: true },
      );
    });
  }

  async function load() {
    if (!isCurrentView()) return;
    const list = el('#list', root);
    if (!list) return;
    list.innerHTML = `<div class="loading-page" style="min-height:120px"><div class="spinner dark"></div></div>`;
    try {
      const res = await api.get(`/geo/nearby?lat=${coords.lat}&lon=${coords.lon}&radius_km=25&category=${category}`);
      if (!isCurrentView()) return;
      places = res.places || [];
      origin = res.origin || coords;
      el('#source-label', root).textContent =
        `Source : ${res.source === 'local-fallback' ? 'Référentiel médical national (Tunisie)' : 'OpenStreetMap / Overpass (En direct)'}`;
      el('#count', root).textContent = `${places.length} établissement${places.length > 1 ? 's' : ''}`;
      
      renderMap();
      renderList();
    } catch (err) {
      if (!isCurrentView()) return;
      list.innerHTML = `<p class="small" style="padding:12px 0">${h(err.message)}</p>`;
      toast(err.message, 'err');
    }
  }

  function renderMap() {
    const container = el('#leaflet-map', root);
    if (window.L && container) {
      renderLeafletMap(container);
    } else {
      drawCanvasFallback();
    }
  }

  function renderLeafletMap(container) {
    try {
      if (!leafletMap) {
        leafletMap = window.L.map(container, {
          center: [origin.lat, origin.lon],
          zoom: 13,
          zoomControl: true,
        });

        // 🛰️ Couche Satellite HD réel (Esri World Imagery)
        satelliteLayer = window.L.tileLayer(
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          {
            maxZoom: 19,
            attribution: 'Imagerie satellite &copy; Esri, Maxar, Earthstar Geographics'
          }
        );

        // 🏷️ Couche noms des rues, villes et repères par-dessus le satellite
        satelliteLabelsLayer = window.L.tileLayer(
          'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
          {
            maxZoom: 19
          }
        );

        // 🗺️ Couche Plan standard des rues (OpenStreetMap)
        streetLayer = window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
        });

        // Mode par défaut : Satellite réel avec labels
        if (currentMapMode === 'satellite') {
          satelliteLayer.addTo(leafletMap);
          satelliteLabelsLayer.addTo(leafletMap);
        } else {
          streetLayer.addTo(leafletMap);
        }

        markersLayer = window.L.layerGroup().addTo(leafletMap);
        setupLayerToggle();
      } else {
        markersLayer.clearLayers();
        leafletMap.setView([origin.lat, origin.lon], 13);
      }

      // Marqueur utilisateur
      const userHtml = `<div style="background:#2563EB; width:24px; height:24px; border-radius:50%; border:3px solid #fff; box-shadow:0 0 12px rgba(37,99,235,0.9); display:flex; align-items:center; justify-content:center; color:#fff; font-size:12px">📍</div>`;
      const userIcon = window.L.divIcon({
        className: 'user-pin',
        html: userHtml,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
      });
      window.L.marker([origin.lat, origin.lon], { icon: userIcon })
        .addTo(markersLayer)
        .bindPopup('<b style="font-size:12px">Votre position actuelle</b><br><span style="font-size:11px; color:#475569">Rayon de recherche : 25 km</span>');

      // Cercle du rayon de 5 km
      window.L.circle([origin.lat, origin.lon], {
        radius: 5000,
        color: '#10B981',
        weight: 2,
        dashArray: '5, 8',
        fillColor: '#10B981',
        fillOpacity: 0.08
      }).addTo(markersLayer);

      const bounds = window.L.latLngBounds([[origin.lat, origin.lon]]);

      places.forEach((p) => {
        bounds.extend([p.lat, p.lon]);
        const color = CAT_COLORS[p.category] || '#2980B9';
        const iconChar = p.emergency_24_7 ? '🚨' : (p.category === 'podiatrist' ? '🦶' : (p.category === 'pharmacy' ? '💊' : '🏥'));
        
        const pinHtml = `<div style="background:${color}; width:28px; height:28px; border-radius:50%; border:2px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.35); display:flex; align-items:center; justify-content:center; font-size:12px; cursor:pointer">${iconChar}</div>`;
        const pinIcon = window.L.divIcon({
          className: 'place-pin',
          html: pinHtml,
          iconSize: [28, 28],
          iconAnchor: [14, 14]
        });

        const marker = window.L.marker([p.lat, p.lon], { icon: pinIcon }).addTo(markersLayer);

        const popup = `
          <div style="font-family:system-ui,-apple-system,sans-serif; min-width:190px; padding:2px">
            <div style="font-size:10px; font-weight:700; color:${color}; text-transform:uppercase">${h(p.category_label)}</div>
            <div style="font-size:13px; font-weight:700; color:#0f172a; margin-top:2px">${h(p.name)}</div>
            <div style="font-size:11px; color:#475569; margin-top:2px"><b>${num(p.distance_km, 1)} km</b> · ${p.emergency_24_7 ? '<span style="color:#dc2626; font-weight:600">Ouvert 24/7</span>' : 'Ouvert'}</div>
            ${p.address ? `<div style="font-size:11px; color:#64748b; margin-top:4px">${h(p.address)}</div>` : ''}
            ${p.phone ? `<div style="margin-top:6px"><a href="tel:${h(p.phone)}" style="font-size:11.5px; color:#0f766e; text-decoration:none; font-weight:600">📞 ${h(p.phone)}</a></div>` : ''}
            <div style="margin-top:8px">
              <a href="https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lon}" target="_blank" rel="noopener" style="display:inline-block; background:#0f766e; color:#fff; font-size:11px; padding:5px 9px; border-radius:5px; text-decoration:none; font-weight:500">📍 Itinéraire Google Maps</a>
            </div>
          </div>`;
        marker.bindPopup(popup);
        marker.on('click', () => select(p));
        p._marker = marker;
      });

      if (places.length > 0) {
        leafletMap.fitBounds(bounds, { padding: [35, 35], maxZoom: 14 });
      }
    } catch (e) {
      console.warn('Leaflet render error, falling back to canvas:', e);
      drawCanvasFallback();
    }
  }

  function setupLayerToggle() {
    const btnSat = el('#btn-satellite', root);
    const btnStr = el('#btn-streets', root);
    if (!btnSat || !btnStr || !leafletMap) return;

    btnSat.onclick = (e) => {
      e.stopPropagation();
      if (currentMapMode === 'satellite') return;
      currentMapMode = 'satellite';
      if (streetLayer && leafletMap.hasLayer(streetLayer)) leafletMap.removeLayer(streetLayer);
      if (satelliteLayer && !leafletMap.hasLayer(satelliteLayer)) satelliteLayer.addTo(leafletMap);
      if (satelliteLabelsLayer && !leafletMap.hasLayer(satelliteLabelsLayer)) satelliteLabelsLayer.addTo(leafletMap);
      btnSat.style.background = '#0f766e';
      btnSat.style.color = '#fff';
      btnStr.style.background = 'transparent';
      btnStr.style.color = '#334155';
    };

    btnStr.onclick = (e) => {
      e.stopPropagation();
      if (currentMapMode === 'streets') return;
      currentMapMode = 'streets';
      if (satelliteLayer && leafletMap.hasLayer(satelliteLayer)) leafletMap.removeLayer(satelliteLayer);
      if (satelliteLabelsLayer && leafletMap.hasLayer(satelliteLabelsLayer)) leafletMap.removeLayer(satelliteLabelsLayer);
      if (streetLayer && !leafletMap.hasLayer(streetLayer)) streetLayer.addTo(leafletMap);
      btnStr.style.background = '#0f766e';
      btnStr.style.color = '#fff';
      btnSat.style.background = 'transparent';
      btnSat.style.color = '#334155';
    };
  }

  function drawCanvasFallback() {
    const canvas = el('#canvas', root);
    if (!canvas) return;
    canvas.style.display = 'block';
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#F3F0E9';
    ctx.fillRect(0, 0, W, H);
  }

  function renderList() {
    const list = el('#list', root);
    if (!places.length) {
      list.innerHTML = `<p class="small" style="padding:14px 0">Aucun établissement répertorié dans un rayon de 25 km.</p>`;
      return;
    }
    list.innerHTML = places.map((p, i) => `
      <button class="patient-row" data-idx="${i}" style="width:100%; text-align:left; align-items:flex-start; padding:12px 6px; cursor:pointer; border-bottom:1px solid var(--border)">
        <span style="width:10px; height:10px; border-radius:50%; margin-top:5px; flex:0 0 auto;
          background:${CAT_COLORS[p.category] || '#2980B9'}"></span>
        <span style="flex:1; min-width:0">
          <span style="display:block; font-size:13px; font-weight:600; color:var(--ink)">${h(p.name)}</span>
          <span style="display:block; font-size:11px; color:var(--ink-2); margin-top:2px">
            <b>${num(p.distance_km, 1)} km</b> · ${h(p.category_label)}${p.emergency_24_7 ? ' · <span style="color:#C0392B; font-weight:600">Urgences 24/7</span>' : ''}</span>
          ${p.address ? `<span style="display:block; font-size:10.5px; color:var(--muted); margin-top:2px">${h(p.address)}</span>` : ''}
          ${p.phone ? `<span style="display:block; font-size:10.5px; color:#0f766e; margin-top:2px; font-weight:500">📞 ${h(p.phone)}</span>` : ''}
        </span>
        ${icon('arrow', 14)}
      </button>`).join('');
    els('[data-idx]', list).forEach((b) =>
      b.addEventListener('click', () => select(places[Number(b.dataset.idx)])));
  }

  function select(p) {
    selected = p;
    if (p._marker && leafletMap) {
      leafletMap.panTo([p.lat, p.lon]);
      p._marker.openPopup();
    }
    const box = el('#detail', root);
    box.style.display = 'block';
    const color = CAT_COLORS[p.category] || '#2980B9';
    box.innerHTML = `
      <div class="row between" style="align-items:flex-start">
        <div>
          <div class="eyebrow" style="color:${color}">${h(p.category_label)}</div>
          <div class="t" style="font-family:var(--serif); font-size:17px; font-weight:600; margin-top:5px">${h(p.name)}</div>
        </div>
        <button class="btn quiet sm" id="close-detail" aria-label="Fermer">${icon('close', 14)}</button>
      </div>
      <div class="small mt-sm"><b>${num(p.distance_km, 1)} km</b> · ${p.emergency_24_7 ? '<span style="color:#C0392B; font-weight:600">Urgences 24/7</span>' : 'Ouvert'}</div>
      ${p.address ? `<div class="tiny mt-sm">${h(p.address)}</div>` : ''}
      ${p.opening_hours ? `<div class="tiny mt-sm">${h(p.opening_hours)}</div>` : ''}
      <div class="row mt" style="gap:8px">
        ${p.phone ? `<a class="btn ghost sm" href="tel:${h(p.phone)}" style="flex:1">${icon('phone', 13)} Appeler</a>` : ''}
        <a class="btn sm" style="flex:1" target="_blank" rel="noopener"
          href="https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lon}">
          ${icon('nav', 13)} Itinéraire Google Maps</a>
      </div>`;
    el('#close-detail', root).addEventListener('click', () => { box.style.display = 'none'; });
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // 1. Détection immédiate de la position réelle
  await locate(false, false);
  if (coords.lat === TUNIS.lat && coords.lon === TUNIS.lon) {
    await load();
  }
}
