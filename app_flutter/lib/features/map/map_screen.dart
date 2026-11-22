import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../data/models/models.dart';
import '../../data/services/api_service.dart';

/// Cartographie des soins de proximité (OpenStreetMap, sans clé API).
class MapScreen extends StatefulWidget {
  const MapScreen({super.key, this.embedded = true});

  final bool embedded;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final _mapController = MapController();
  LatLng _center = const LatLng(36.8065, 10.1815); // Tunis par défaut
  List<CarePlace> _places = [];
  String _category = 'all';
  bool _loading = true;
  String? _error;
  bool _locating = true;
  CarePlace? _focused;

  static const _filters = <String, String>{
    'all': 'Tous',
    'emergency': 'Urgences 24/7',
    'wound_care': 'Plaies & cicatrisation',
    'podiatrist': 'Podologues',
    'diabetologist': 'Diabétologues',
  };

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await _locate();
    await _load();
  }

  /// ⚠️ Sur Web, on n'appelle JAMAIS `Permission.location.request()` : le
  /// navigateur affiche lui-même sa boîte de dialogue. On interroge simplement
  /// la position courante, avec un repli sur le centre-ville par défaut.
  Future<void> _locate() async {
    setState(() => _locating = true);
    try {
      if (!kIsWeb) {
        final serviceEnabled = await Geolocator.isLocationServiceEnabled();
        if (serviceEnabled) {
          var permission = await Geolocator.checkPermission();
          if (permission == LocationPermission.denied) {
            permission = await Geolocator.requestPermission();
          }
          if (permission == LocationPermission.denied ||
              permission == LocationPermission.deniedForever) {
            setState(() => _locating = false);
            return;
          }
        }
      }
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.medium,
        timeLimit: const Duration(seconds: 12),
      );
      setState(() => _center = LatLng(position.latitude, position.longitude));
    } catch (_) {
      // Position indisponible : on conserve le centre par défaut.
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final places = await context.read<ApiService>().nearbyPlaces(
            lat: _center.latitude,
            lon: _center.longitude,
            radiusKm: 25,
            category: _category,
          );
      if (!mounted) return;
      setState(() {
        _places = places;
        _loading = false;
        _focused = places.isNotEmpty ? places.first : null;
      });
      _mapController.move(_center, 12.4);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = Column(
      children: [
        SizedBox(
          height: 40,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: _filters.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, i) {
              final key = _filters.keys.elementAt(i);
              final selected = key == _category;
              return GestureDetector(
                onTap: () {
                  setState(() => _category = key);
                  _load();
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  alignment: Alignment.center,
                  padding: const EdgeInsets.symmetric(horizontal: 15),
                  decoration: BoxDecoration(
                    gradient: selected ? DfGradients.copperSheen : null,
                    color: selected ? null : DfColors.plumSoft,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(
                        color:
                            selected ? Colors.transparent : DfColors.hairline),
                  ),
                  child: Text(
                    _filters[key]!,
                    style: DfType.caption.copyWith(
                      fontSize: 11,
                      color: selected ? DfColors.ink : DfColors.creamDim,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 12),
        Expanded(
          child: Stack(
            children: [
              FlutterMap(
                mapController: _mapController,
                options: MapOptions(
                  initialCenter: _center,
                  initialZoom: 12.4,
                  minZoom: 3,
                  maxZoom: 18,
                  onTap: (_, __) => setState(() => _focused = null),
                  interactionOptions: const InteractionOptions(
                    flags: InteractiveFlag.drag |
                        InteractiveFlag.pinchZoom |
                        InteractiveFlag.doubleTapZoom,
                  ),
                ),
                children: [
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'health.diafoot.sentinel',
                    tileProvider: NetworkTileProvider(),
                  ),
                  MarkerLayer(
                    markers: [
                      Marker(
                        point: _center,
                        width: 26,
                        height: 26,
                        child: Container(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: DfColors.info,
                            border: Border.all(color: Colors.white, width: 2),
                            boxShadow: [
                              BoxShadow(
                                color: DfColors.info.withValues(alpha: 0.5),
                                blurRadius: 12,
                              ),
                            ],
                          ),
                        ),
                      ),
                      for (final place in _places)
                        Marker(
                          point: LatLng(place.lat, place.lon),
                          width: 40,
                          height: 40,
                          child: GestureDetector(
                            onTap: () {
                              setState(() => _focused = place);
                              _mapController.move(
                                  LatLng(place.lat, place.lon), 14.5);
                            },
                            child: _marker(place),
                          ),
                        ),
                    ],
                  ),
                  RichAttributionWidget(
                    attributions: [
                      TextSourceAttribution('© OpenStreetMap', onTap: () {}),
                    ],
                  ),
                ],
              ),
              if (_loading || _locating)
                Container(
                  color: DfColors.ink.withValues(alpha: 0.55),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(strokeWidth: 1.6),
                        ),
                        const SizedBox(height: 14),
                        Text(
                          _locating
                              ? 'Localisation en cours…'
                              : 'Recherche des centres de soins…',
                          style: DfType.caption,
                        ),
                      ],
                    ),
                  ),
                ),
              if (_error != null)
                Positioned(
                  left: 16,
                  right: 16,
                  top: 16,
                  child: DfGlassCard(
                    accent: DfColors.critical,
                    padding: const EdgeInsets.all(14),
                    child: Text(_error!, style: DfType.caption),
                  ),
                ),
              Positioned(
                right: 14,
                bottom: 14,
                child: Column(
                  children: [
                    _mapButton(
                      Icons.my_location_rounded,
                      () async {
                        await _locate();
                        _mapController.move(_center, 13);
                        await _load();
                      },
                    ),
                    const SizedBox(height: 8),
                    _mapButton(
                        Icons.add_rounded,
                        () => _mapController.move(_mapController.camera.center,
                            _mapController.camera.zoom + 1)),
                    const SizedBox(height: 8),
                    _mapButton(
                        Icons.remove_rounded,
                        () => _mapController.move(_mapController.camera.center,
                            _mapController.camera.zoom - 1)),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (_focused != null)
          _PlaceSheet(
              place: _focused!, onClose: () => setState(() => _focused = null))
        else
          SizedBox(
            height: 108,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              itemCount: _places.length,
              separatorBuilder: (_, __) => const SizedBox(width: 10),
              itemBuilder: (context, i) {
                final p = _places[i];
                return GestureDetector(
                  onTap: () {
                    setState(() => _focused = p);
                    _mapController.move(LatLng(p.lat, p.lon), 15);
                  },
                  child: Container(
                    width: 210,
                    padding: const EdgeInsets.all(13),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(14),
                      color: DfColors.plumSoft,
                      border: Border.all(color: DfColors.hairline),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(p.name,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: DfType.bodyStrong.copyWith(fontSize: 11.5)),
                        const Spacer(),
                        Text(
                          '${p.categoryLabel} · ${p.distanceKm.toStringAsFixed(1)} km',
                          style: DfType.caption.copyWith(fontSize: 9.5),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
      ],
    );

    if (widget.embedded) {
      return DfContentFrame(
          maxWidth: 900, padding: EdgeInsets.zero, child: content);
    }
    return Scaffold(
      body: DfScaffoldBackground(
        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 6, 16, 2),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.arrow_back_rounded,
                          color: DfColors.creamDim),
                    ),
                    Text('Centres & urgences',
                        style: DfType.h3.copyWith(fontSize: 16)),
                  ],
                ),
              ),
              Expanded(child: content),
            ],
          ),
        ),
      ),
    );
  }

  Widget _marker(CarePlace place) {
    final color = place.emergency247
        ? DfColors.critical
        : switch (place.category) {
            'pharmacy' => DfColors.stable,
            'podiatrist' => DfColors.copperLight,
            _ => DfColors.champagne,
          };
    return Container(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: DfColors.ink, width: 1.6),
        boxShadow: [
          BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 10),
        ],
      ),
      child: Icon(
        place.emergency247
            ? Icons.local_hospital_rounded
            : Icons.medical_services_outlined,
        size: 16,
        color: DfColors.ink,
      ),
    );
  }

  Widget _mapButton(IconData icon, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: DfColors.plum.withValues(alpha: 0.94),
          borderRadius: BorderRadius.circular(11),
          border: Border.all(color: DfColors.hairline),
        ),
        child: Icon(icon, size: 17, color: DfColors.champagne),
      ),
    );
  }
}

class _PlaceSheet extends StatelessWidget {
  const _PlaceSheet({required this.place, required this.onClose});

  final CarePlace place;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
      child: DfGlassCard(
        accent: place.emergency247 ? DfColors.critical : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child:
                      Text(place.name, style: DfType.h3.copyWith(fontSize: 16)),
                ),
                GestureDetector(
                  onTap: onClose,
                  child: const Icon(Icons.close_rounded,
                      size: 17, color: DfColors.muted),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${place.categoryLabel} · ${place.distanceKm.toStringAsFixed(1)} km'
              '${place.emergency247 ? ' · Urgences 24/7' : ''}',
              style: DfType.caption.copyWith(fontSize: 10.5),
            ),
            if (place.address != null) ...[
              const SizedBox(height: 6),
              Text(place.address!,
                  style: DfType.caption.copyWith(fontSize: 10)),
            ],
            if (place.openingHours != null) ...[
              const SizedBox(height: 4),
              Text('Horaires : ${place.openingHours!}',
                  style: DfType.caption.copyWith(fontSize: 10)),
            ],
            const SizedBox(height: 14),
            Row(
              children: [
                if (place.phone != null)
                  Expanded(
                    child: DfGhostButton(
                      label: 'Appeler',
                      icon: Icons.call_outlined,
                      onPressed: () =>
                          launchUrl(Uri.parse('tel:${place.phone}')),
                    ),
                  ),
                if (place.phone != null) const SizedBox(width: 10),
                Expanded(
                  child: DfGhostButton(
                    label: 'Itinéraire',
                    icon: Icons.directions_outlined,
                    onPressed: () => launchUrl(
                      Uri.parse(
                        'https://www.openstreetmap.org/directions?to=${place.lat},${place.lon}',
                      ),
                      mode: LaunchMode.externalApplication,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
