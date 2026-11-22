import 'dart:async';
import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:sensors_plus/sensors_plus.dart';

import '../../core/config/app_config.dart';
import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../core/utils/platform_image.dart';
import '../../data/models/models.dart';
import '../../state/app_state.dart';

/// Charge utile transmise à l'écran de résultats : **uniquement des octets**,
/// jamais un chemin système (compatibilité Web garantie).
class AnalysisLaunchResult {
  const AnalysisLaunchResult({
    required this.woundId,
    required this.woundLabel,
    required this.imageBytes,
    required this.filename,
    required this.scaleRefCm,
  });

  final int woundId;
  final String woundLabel;
  final Uint8List imageBytes;
  final String filename;
  final double scaleRefCm;
}

/// Protocole de capture guidée : caméra temps réel (mobile) ou dépôt de
/// fichier HTML5 (Web), avec cadrage, niveau à bulle et contrôle qualité.
class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  CameraController? _controller;
  Future<void>? _initFuture;
  bool _cameraUnavailable = kIsWeb;
  String? _cameraError;
  bool _torchOn = false;
  bool _capturing = false;

  double _tiltDeg = 0;
  StreamSubscription<AccelerometerEvent>? _accelSub;

  Uint8List? _previewBytes;
  String _previewName = 'wound.jpg';

  Wound? _wound;
  double _scaleRef = AppConfig.defaultScaleRefCm;
  final _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    final wounds = context.read<WoundProvider>().wounds;
    _wound = wounds.isNotEmpty ? wounds.first : null;
    _listenTilt();
    if (!kIsWeb) _initCamera();
  }

  void _listenTilt() {
    _accelSub = accelerometerEventStream().listen((event) {
      // Angle entre la normale de l'écran et la gravité : 0° = téléphone
      // parfaitement parallèle à la surface photographiée.
      final magnitude = math.sqrt(
        event.x * event.x + event.y * event.y + event.z * event.z,
      );
      if (magnitude < 0.1) return;
      final tilt =
          math.acos((event.z / magnitude).clamp(-1.0, 1.0)) * 180 / math.pi;
      if (!mounted) return;
      setState(() => _tiltDeg = tilt > 90 ? 180 - tilt : tilt);
    }, onError: (_) {});
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() => _cameraUnavailable = true);
        return;
      }
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      final controller = CameraController(
        back,
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );
      _initFuture = controller.initialize();
      await _initFuture;
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _cameraUnavailable = false;
      });
    } catch (error) {
      setState(() {
        _cameraUnavailable = true;
        _cameraError = 'Caméra indisponible : $error';
      });
    }
  }

  @override
  void dispose() {
    _accelSub?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  bool get _framingOk => _tiltDeg.abs() <= AppConfig.targetAngleTolerance;

  @override
  Widget build(BuildContext context) {
    final wounds = context.watch<WoundProvider>().wounds;
    if (_wound == null && wounds.isNotEmpty) _wound = wounds.first;

    return Scaffold(
      backgroundColor: DfColors.ink,
      body: DfSafeGradient(
        child: SafeArea(
          child: Column(
            children: [
              _header(context),
              Expanded(
                child: DfContentFrame(
                  maxWidth: 620,
                  child: Column(
                    children: [
                      Expanded(
                        child: _previewBytes != null
                            ? _reviewPreview()
                            : (_cameraUnavailable
                                ? _uploadZone()
                                : _cameraPreview()),
                      ),
                      const SizedBox(height: 16),
                      _controls(wounds),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _header(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 16, 2),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.close_rounded, color: DfColors.creamDim),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('CAPTURE GUIDÉE',
                    style: DfType.overline.copyWith(fontSize: 8.5)),
                const SizedBox(height: 3),
                Text('Photographier la plaie',
                    style: DfType.h3.copyWith(fontSize: 16)),
              ],
            ),
          ),
          if (!_cameraUnavailable && _controller != null)
            IconButton(
              onPressed: _toggleTorch,
              icon: Icon(
                _torchOn ? Icons.flash_on_rounded : Icons.flash_off_rounded,
                color: _torchOn ? DfColors.copperLight : DfColors.muted,
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _toggleTorch() async {
    final controller = _controller;
    if (controller == null) return;
    try {
      await controller.setFlashMode(_torchOn ? FlashMode.off : FlashMode.torch);
      setState(() => _torchOn = !_torchOn);
    } catch (_) {
      // torche non supportée par l'objectif : ignoré silencieusement
    }
  }

  // -----------------------------------------------------------------------
  // Caméra temps réel (mobile)
  // -----------------------------------------------------------------------
  Widget _cameraPreview() {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return Center(
        child: FutureBuilder<void>(
          future: _initFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.done) {
              return Text('Initialisation de la caméra…',
                  style: DfType.caption);
            }
            return const CircularProgressIndicator(strokeWidth: 1.6);
          },
        ),
      );
    }

    final previewSize = controller.value.previewSize;
    final aspect =
        previewSize == null ? 1.0 : previewSize.width / previewSize.height;

    return ClipRRect(
      borderRadius: BorderRadius.circular(22),
      child: Stack(
        fit: StackFit.expand,
        children: [
          FittedBox(
            fit: BoxFit.cover,
            child: SizedBox(
              width: previewSize?.height ?? 1,
              height: previewSize?.width ?? 1,
              child: AspectRatio(
                aspectRatio: 1 / aspect,
                child: CameraPreview(controller),
              ),
            ),
          ),
          // Guide de cadrage semi-transparent
          Positioned.fill(
            child: CustomPaint(
              painter: _FramingGuidePainter(
                alignment: _framingOk ? DfColors.stable : DfColors.copperLight,
              ),
            ),
          ),
          Positioned(
            left: 14,
            right: 14,
            top: 14,
            child: _LevelIndicator(tilt: _tiltDeg, ok: _framingOk),
          ),
          Positioned(
            left: 14,
            right: 14,
            bottom: 14,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
              decoration: BoxDecoration(
                color: DfColors.ink.withValues(alpha: 0.62),
                borderRadius: BorderRadius.circular(11),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline_rounded,
                      size: 13, color: DfColors.copperLight),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Placez la gommette verte de 2 cm près de la plaie, '
                      'au centre de la cible.',
                      style: DfType.caption.copyWith(fontSize: 10),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _takePicture() async {
    final controller = _controller;
    if (controller == null || _capturing) return;
    setState(() => _capturing = true);
    try {
      final file = await controller.takePicture();
      // ⚠️ readAsBytes() : fonctionne sur mobile ET sur Web (XFile)
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      setState(() {
        _previewBytes = bytes;
        _previewName = 'wound_${DateTime.now().millisecondsSinceEpoch}.jpg';
      });
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Prise de vue impossible : $error')),
      );
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  // -----------------------------------------------------------------------
  // Zone de dépôt (Web & secours mobile)
  // -----------------------------------------------------------------------
  Widget _uploadZone() {
    return DragTarget<Object>(
      onAcceptWithDetails: (details) async {
        final data = details.data;
        if (data is XFile) {
          final bytes = await data.readAsBytes();
          setState(() {
            _previewBytes = bytes;
            _previewName = data.name;
          });
        }
      },
      builder: (context, candidate, rejected) {
        final active = candidate.isNotEmpty;
        return DfGlassCard(
          accent: active ? DfColors.copper : null,
          padding: EdgeInsets.zero,
          child: InkWell(
            onTap: _pickFromGallery,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  active ? Icons.download_rounded : Icons.cloud_upload_outlined,
                  size: 46,
                  color: active
                      ? DfColors.copperLight
                      : DfColors.copper.withValues(alpha: 0.7),
                ),
                const SizedBox(height: 18),
                Text(
                  active ? 'Déposez l\'image' : 'Glissez-déposez votre photo',
                  style: DfType.h3,
                ),
                const SizedBox(height: 8),
                Text(
                  'JPEG ou PNG · 15 Mo max\n'
                  'ou cliquez pour sélectionner un fichier',
                  textAlign: TextAlign.center,
                  style: DfType.caption.copyWith(height: 1.6),
                ),
                if (_cameraError != null) ...[
                  const SizedBox(height: 16),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: Text(
                      _cameraError!,
                      textAlign: TextAlign.center,
                      style: DfType.caption.copyWith(fontSize: 9.5),
                    ),
                  ),
                ],
                const SizedBox(height: 22),
                DfGhostButton(
                  label: 'Importer une photo',
                  icon: Icons.photo_library_outlined,
                  onPressed: _pickFromGallery,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _pickFromGallery() async {
    try {
      final file = await _picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 2200,
        imageQuality: 92,
      );
      if (file == null) return;
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      setState(() {
        _previewBytes = bytes;
        _previewName = file.name.isEmpty ? 'wound.jpg' : file.name;
      });
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sélection impossible : $error')),
      );
    }
  }

  Widget _reviewPreview() {
    return DfGlassCard(
      padding: EdgeInsets.zero,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Stack(
          fit: StackFit.expand,
          children: [
            buildWoundImage(_previewBytes, fit: BoxFit.contain),
            Positioned(
              top: 12,
              right: 12,
              child: DfGhostButton(
                label: 'Reprendre',
                icon: Icons.refresh_rounded,
                onPressed: () => setState(() => _previewBytes = null),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // -----------------------------------------------------------------------
  Widget _controls(List<Wound> wounds) {
    return Column(
      children: [
        DfGlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              const Icon(Icons.healing_outlined,
                  size: 16, color: DfColors.copper),
              const SizedBox(width: 10),
              Expanded(
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<Wound>(
                    value: _wound,
                    isExpanded: true,
                    dropdownColor: DfColors.plumLift,
                    style: DfType.body
                        .copyWith(color: DfColors.cream, fontSize: 12.5),
                    hint: Text('Sélectionner une plaie', style: DfType.caption),
                    items: [
                      for (final w in wounds)
                        DropdownMenuItem(value: w, child: Text(w.label)),
                    ],
                    onChanged: (w) => setState(() => _wound = w),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Container(width: 0.8, height: 22, color: DfColors.hairline),
              const SizedBox(width: 12),
              Text('Repère', style: DfType.caption.copyWith(fontSize: 10)),
              const SizedBox(width: 8),
              DropdownButtonHideUnderline(
                child: DropdownButton<double>(
                  value: _scaleRef,
                  dropdownColor: DfColors.plumLift,
                  style: DfType.bodyStrong.copyWith(fontSize: 12),
                  items: const [
                    DropdownMenuItem(value: 1.0, child: Text('1,0 cm')),
                    DropdownMenuItem(value: 2.0, child: Text('2,0 cm')),
                    DropdownMenuItem(value: 5.0, child: Text('5,0 cm (ArUco)')),
                  ],
                  onChanged: (v) => setState(() => _scaleRef = v ?? 2.0),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        if (_previewBytes != null)
          DfPrimaryButton(
            label: 'Analyser cette image',
            icon: Icons.auto_awesome_rounded,
            expand: true,
            pulse: true,
            onPressed: _submit,
          )
        else if (!_cameraUnavailable)
          GestureDetector(
            onTap: _takePicture,
            child: Container(
              width: 74,
              height: 74,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: _framingOk ? DfColors.stable : DfColors.copperLight,
                  width: 3,
                ),
              ),
              child: Center(
                child: Container(
                  width: 58,
                  height: 58,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: DfGradients.copperSheen,
                  ),
                  child: _capturing
                      ? const Padding(
                          padding: EdgeInsets.all(18),
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(DfColors.ink),
                          ),
                        )
                      : const Icon(Icons.camera_rounded,
                          color: DfColors.ink, size: 24),
                ),
              ),
            ),
          ),
        const SizedBox(height: 10),
        const DfdDisclaimer(compact: true),
        const SizedBox(height: 6),
      ],
    );
  }

  void _submit() {
    final bytes = _previewBytes;
    final wound = _wound;
    if (bytes == null) return;
    if (wound == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Créez d\'abord une plaie à suivre.')),
      );
      return;
    }
    Navigator.of(context).pop(
      AnalysisLaunchResult(
        woundId: wound.id,
        woundLabel: wound.label,
        imageBytes: bytes,
        filename: _previewName,
        scaleRefCm: _scaleRef,
      ),
    );
  }
}

/// Enveloppe de fond pour les écrans plein écran de capture.
class DfSafeGradient extends StatelessWidget {
  const DfSafeGradient({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: DfGradients.plumVeil),
      child: child,
    );
  }
}

/// Guide de cadrage : cible en forme de pied + coins de visée.
class _FramingGuidePainter extends CustomPainter {
  _FramingGuidePainter({required this.alignment});

  final Color alignment;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final r = math.min(size.width, size.height) * 0.34;

    // Ombre portée douce autour de la cible
    final veil = Paint()
      ..shader = RadialGradient(
        colors: [Colors.transparent, DfColors.ink.withValues(alpha: 0.55)],
        stops: const [0.62, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: r * 1.75));
    canvas.drawRect(Offset.zero & size, veil);

    // Empreinte de pied stylisée (ellipse + talon)
    final foot = Path()
      ..addOval(Rect.fromCenter(
          center: center.translate(0, -r * 0.18),
          width: r * 1.16,
          height: r * 1.5))
      ..addOval(Rect.fromCenter(
          center: center.translate(0, r * 0.82),
          width: r * 0.78,
          height: r * 0.66));
    final footPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..color = alignment.withValues(alpha: 0.85);
    canvas.drawPath(foot, footPaint);

    // Réticule central
    final cross = Paint()
      ..strokeWidth = 1.2
      ..color = alignment.withValues(alpha: 0.7);
    canvas.drawLine(center.translate(-14, 0), center.translate(-5, 0), cross);
    canvas.drawLine(center.translate(5, 0), center.translate(14, 0), cross);
    canvas.drawLine(center.translate(0, -14), center.translate(0, -5), cross);
    canvas.drawLine(center.translate(0, 5), center.translate(0, 14), cross);

    // Coins de visée
    final corner = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.4
      ..strokeCap = StrokeCap.round
      ..color = alignment;
    const len = 26.0;
    const tl = Offset(14, 14);
    final tr = Offset(size.width - 14, 14);
    final bl = Offset(14, size.height - 14);
    final br = Offset(size.width - 14, size.height - 14);
    canvas.drawLine(tl, tl.translate(len, 0), corner);
    canvas.drawLine(tl, tl.translate(0, len), corner);
    canvas.drawLine(tr, tr.translate(-len, 0), corner);
    canvas.drawLine(tr, tr.translate(0, len), corner);
    canvas.drawLine(bl, bl.translate(len, 0), corner);
    canvas.drawLine(bl, bl.translate(0, -len), corner);
    canvas.drawLine(br, br.translate(-len, 0), corner);
    canvas.drawLine(br, br.translate(0, -len), corner);
  }

  @override
  bool shouldRepaint(covariant _FramingGuidePainter old) =>
      old.alignment != alignment;
}

/// Niveau à bulle gyroscopique (parallélisme de la prise de vue).
class _LevelIndicator extends StatelessWidget {
  const _LevelIndicator({required this.tilt, required this.ok});

  final double tilt;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    final color = ok ? DfColors.stable : DfColors.moderate;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: DfColors.ink.withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 26,
            height: 26,
            child:
                CustomPaint(painter: _BubblePainter(tilt: tilt, color: color)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              ok
                  ? 'Plan parallèle — cadrage optimal'
                  : 'Inclinez le téléphone à plat (${tilt.toStringAsFixed(0)}°)',
              style: DfType.caption.copyWith(fontSize: 10, color: color),
            ),
          ),
        ],
      ),
    );
  }
}

class _BubblePainter extends CustomPainter {
  _BubblePainter({required this.tilt, required this.color});

  final double tilt;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.width / 2 - 2;
    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = DfColors.muted.withValues(alpha: 0.6),
    );
    canvas.drawCircle(
      center,
      radius * 0.42,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = color.withValues(alpha: 0.55),
    );
    final offset = Offset(
      (tilt / 45).clamp(-1.0, 1.0) * radius * 0.55,
      0,
    );
    canvas.drawCircle(
      center + offset,
      3.4,
      Paint()..color = color,
    );
  }

  @override
  bool shouldRepaint(covariant _BubblePainter old) =>
      old.tilt != tilt || old.color != color;
}
