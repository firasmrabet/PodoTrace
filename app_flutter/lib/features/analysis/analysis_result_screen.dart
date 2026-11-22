import 'package:flutter/material.dart';
import 'package:printing/printing.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../core/utils/platform_image.dart';
import '../../data/models/models.dart';
import '../../state/app_state.dart';
import '../capture/capture_screen.dart';
import '../chat/chat_screen.dart';

/// Écran de résultats : visualiseur multi-couches, jauges, facteurs de risque
/// et actions cliniques.
class AnalysisResultScreen extends StatefulWidget {
  const AnalysisResultScreen({super.key, required this.result});

  final AnalysisLaunchResult result;

  @override
  State<AnalysisResultScreen> createState() => _AnalysisResultScreenState();
}

class _AnalysisResultScreenState extends State<AnalysisResultScreen> {
  AnalysisResult? _data;
  String? _error;
  String _layer = 'Tissus';
  String? _selectedTissue;

  static const _layers = <String, String>{
    'Originale': 'original',
    'Détourage': 'contour',
    'Tissus': 'segmentation',
    'Grad-CAM': 'heatmap',
  };

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _run());
  }

  Future<void> _run() async {
    final provider = context.read<WoundProvider>();
    final result = await provider.analyse(
      woundId: widget.result.woundId,
      imageBytes: widget.result.imageBytes,
      filename: widget.result.filename,
      scaleRef: widget.result.scaleRefCm,
    );
    if (!mounted) return;
    setState(() {
      _data = result;
      _error =
          result == null ? (provider.error ?? 'Analyse impossible.') : null;
    });
  }

  @override
  Widget build(BuildContext context) {
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
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('RÉSULTAT D\'ANALYSE',
                              style: DfType.overline.copyWith(fontSize: 8.5)),
                          const SizedBox(height: 3),
                          Text(widget.result.woundLabel,
                              style: DfType.h3.copyWith(fontSize: 16),
                              overflow: TextOverflow.ellipsis),
                        ],
                      ),
                    ),
                    if (_data != null)
                      DfRiskPill(level: _data!.analysis.riskLevel),
                  ],
                ),
              ),
              Expanded(child: _body()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _body() {
    if (_error != null) {
      return DfContentFrame(
        child: Center(
          child: DfGlassCard(
            accent: DfColors.critical,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline_rounded,
                    color: DfColors.critical, size: 30),
                const SizedBox(height: 16),
                Text('Analyse non aboutie', style: DfType.h3),
                const SizedBox(height: 10),
                Text(_error!,
                    textAlign: TextAlign.center, style: DfType.caption),
                const SizedBox(height: 20),
                DfGhostButton(
                  label: 'Reprendre la photo',
                  icon: Icons.refresh_rounded,
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
        ),
      );
    }
    if (_data == null) return const _AnalyzingView();

    final data = _data!;
    final a = data.analysis;
    return ListView(
      padding: const EdgeInsets.fromLTRB(0, 4, 0, 40),
      children: [
        DfContentFrame(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // --- Visualiseur multi-couches ---------------------------
              DfGlassCard(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    AspectRatio(
                      aspectRatio: 1,
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 320),
                          child: _layerView(_layers[_layer]!),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    DfSegmentedTabs(
                      tabs: _layers.keys.toList(),
                      value: _layer,
                      onChanged: (v) => setState(() => _layer = v),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _layerCaption(),
                      style: DfType.caption.copyWith(fontSize: 10),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              // --- Risque global + métriques --------------------------
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  DfGlassCard(
                    padding: const EdgeInsets.all(16),
                    child: DfRiskGauge(
                      value: a.globalScore,
                      level: a.riskLevel,
                      size: 132,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      children: [
                        DfMetricTile(
                          label: 'Surface',
                          value: a.areaCm2.toStringAsFixed(2),
                          unit: 'cm²',
                          footnote:
                              'Périmètre ${a.perimeterCm.toStringAsFixed(1)} cm',
                        ),
                        const SizedBox(height: 10),
                        DfMetricTile(
                          label: 'Risque infectieux',
                          value: '${(a.infectionRisk * 100).round()}',
                          unit: '%',
                          footnote:
                              'Ischémique ${(a.ischemiaRisk * 100).round()} %',
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // --- Composition tissulaire -----------------------------
              DfGlassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('COMPOSITION TISSULAIRE',
                        style: DfType.overline.copyWith(fontSize: 9)),
                    const SizedBox(height: 16),
                    DfTissueDonut(
                      composition: a.composition,
                      selected: _selectedTissue,
                      onSelect: (v) => setState(() => _selectedTissue = v),
                    ),
                    if (_selectedTissue != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _tissueAdvice(_selectedTissue!),
                        style: DfType.caption.copyWith(height: 1.6),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // --- Qualité & calibrage --------------------------------
              DfGlassCard(
                child: Row(
                  children: [
                    _metaChip(
                      Icons.straighten_rounded,
                      'Calibrage',
                      data.calibration['method'] == 'aruco'
                          ? 'ArUco'
                          : data.calibration['method'] == 'green_dot'
                              ? 'Gommette verte'
                              : 'Estimation',
                    ),
                    _metaChip(
                      Icons.high_quality_outlined,
                      'Qualité',
                      '${(((data.quality['score'] as num?)?.toDouble() ?? 1.0) * 100).round()} %',
                    ),
                    _metaChip(
                      Icons.bolt_outlined,
                      'Moteur',
                      '${data.processingMs} ms',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 22),

              // --- Facteurs & recommandations -------------------------
              if (a.factors.isNotEmpty) ...[
                const DfSectionTitle(
                  overline: 'Lecture clinique',
                  title: 'Points d\'attention',
                ),
                const SizedBox(height: 14),
                for (final f in a.factors) ...[
                  _FactorTile(factor: f),
                  const SizedBox(height: 9),
                ],
                const SizedBox(height: 14),
              ],
              if (a.recommendations.isNotEmpty) ...[
                DfGlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('CONDUITE À TENIR (IWGDF)',
                          style: DfType.overline.copyWith(fontSize: 9)),
                      const SizedBox(height: 12),
                      for (var i = 0; i < a.recommendations.length; i++)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('${i + 1}.',
                                  style: DfType.bodyStrong.copyWith(
                                      color: DfColors.copper, fontSize: 12)),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(a.recommendations[i],
                                    style:
                                        DfType.caption.copyWith(height: 1.6)),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
              ],
              if (a.uncertainty > 0.12)
                DfGlassCard(
                  accent: DfColors.info,
                  child: Row(
                    children: [
                      const Icon(Icons.help_outline_rounded,
                          size: 16, color: DfColors.info),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Incertitude du modèle élevée (±${a.uncertainty.toStringAsFixed(2)}). '
                          'Un avis médical complémentaire est recommandé.',
                          style: DfType.caption.copyWith(height: 1.5),
                        ),
                      ),
                    ],
                  ),
                ),

              // --- Actions --------------------------------------------
              const SizedBox(height: 22),
              DfPrimaryButton(
                label: 'Enregistrer dans le dossier',
                icon: Icons.save_alt_rounded,
                expand: true,
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                          'Analyse enregistrée et horodatée dans le dossier.'),
                    ),
                  );
                  Navigator.of(context).pop();
                },
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: DfGhostButton(
                      label: 'Question à l\'IA',
                      icon: Icons.auto_awesome_outlined,
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ChatScreen(
                            embedded: false,
                            woundId: widget.result.woundId,
                            contextLabel: widget.result.woundLabel,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: DfGhostButton(
                      label: 'Rapport PDF',
                      icon: Icons.picture_as_pdf_outlined,
                      onPressed: () => _sharePdf(widget.result.woundId),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(data.disclaimer,
                  style: DfType.caption.copyWith(height: 1.6)),
              const SizedBox(height: 10),
            ],
          ),
        ),
      ],
    );
  }

  Widget _layerView(String variant) {
    final bytes = _data!.bytesFor(variant);
    return Container(
      key: ValueKey(variant),
      color: DfColors.plumSoft,
      child: bytes == null
          ? const DfImageFallback()
          : buildWoundImage(bytes, fit: BoxFit.cover),
    );
  }

  String _layerCaption() {
    switch (_layer) {
      case 'Tissus':
        return 'Segmentation multi-tissus — nécrose, fibrine, granulation, épithélialisation';
      case 'Grad-CAM':
        return 'Carte d\'attention clinique : zones ayant déclenché le score de risque';
      case 'Détourage':
        return 'Contour précis de la plaie utilisé pour la planimétrie';
      default:
        return 'Photographie originale recadrée et redressée';
    }
  }

  String _tissueAdvice(String key) {
    switch (key) {
      case 'granulation':
        return 'Tissu de granulation : bourgeonnement rouge vif, signe d\'une cicatrisation active.';
      case 'fibrin':
        return 'Fibrine / slough : tissu dévitalisé adhérent. Un débridement favorise l\'épithélialisation.';
      case 'necrosis':
        return 'Nécrose : tissu mort à réséquer, après évaluation vasculaire. Risque infectieux majoré.';
      case 'epithelial':
        return 'Épithélialisation : berges roses en cours de fermeture, bon pronostic local.';
      default:
        return '';
    }
  }

  Widget _metaChip(IconData icon, String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Icon(icon, size: 16, color: DfColors.copper.withValues(alpha: 0.85)),
          const SizedBox(height: 8),
          Text(label.toUpperCase(),
              style: DfType.caption.copyWith(fontSize: 8)),
          const SizedBox(height: 4),
          Text(value,
              style: DfType.bodyStrong.copyWith(fontSize: 11.5),
              textAlign: TextAlign.center),
        ],
      ),
    );
  }

  Future<void> _sharePdf(int woundId) async {
    final provider = context.read<WoundProvider>();
    final bytes = await provider.reportPdf(woundId);
    if (!mounted) return;
    if (bytes == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(provider.error ?? 'Export impossible.')),
      );
      return;
    }
    await Printing.sharePdf(
        bytes: bytes, filename: 'DiaFoot_Sentinel_rapport.pdf');
  }
}

class _FactorTile extends StatelessWidget {
  const _FactorTile({required this.factor});

  final RiskFactor factor;

  @override
  Widget build(BuildContext context) {
    final color = switch (factor.severity) {
      'critical' => DfColors.critical,
      'positive' => DfColors.stable,
      _ => DfColors.moderate,
    };
    final icon = switch (factor.severity) {
      'critical' => Icons.priority_high_rounded,
      'positive' => Icons.check_rounded,
      _ => Icons.circle_outlined,
    };
    return DfGlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 26,
            height: 26,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 14, color: color),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(factor.label,
                    style: DfType.bodyStrong.copyWith(fontSize: 12.5)),
                const SizedBox(height: 4),
                Text(factor.detail,
                    style: DfType.caption.copyWith(height: 1.5)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Écran d'attente pendant l'inférence (étapes du pipeline).
class _AnalyzingView extends StatefulWidget {
  const _AnalyzingView();

  @override
  State<_AnalyzingView> createState() => _AnalyzingViewState();
}

class _AnalyzingViewState extends State<_AnalyzingView>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 6),
  );

  static const _steps = [
    'Contrôle de qualité de l\'image',
    'Segmentation multi-tissus (U-Net++)',
    'Calibrage métrique et planimétrie',
    'Évaluation des risques infectieux et ischémiques',
    'Génération de la carte d\'explicabilité',
  ];

  int _step = 0;
  double _progress = 0;

  @override
  void initState() {
    super.initState();
    _c.addListener(() {
      final t = _c.value;
      setState(() {
        _progress = t;
        _step = (t * _steps.length).floor().clamp(0, _steps.length - 1);
      });
    });
    _c.forward();
    _c.addStatusListener((status) {
      if (status == AnimationStatus.completed) _c.forward(from: 0.15);
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return DfContentFrame(
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 84,
              height: 84,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 84,
                    height: 84,
                    child: CircularProgressIndicator(
                      value: _progress,
                      strokeWidth: 2,
                      backgroundColor: DfColors.hairline,
                    ),
                  ),
                  const Icon(Icons.auto_awesome_rounded,
                      color: DfColors.copperLight, size: 26),
                ],
              ),
            ),
            const SizedBox(height: 30),
            Text('Analyse en cours', style: DfType.h2),
            const SizedBox(height: 10),
            Text(_steps[_step],
                style: DfType.caption.copyWith(color: DfColors.champagne)),
            const SizedBox(height: 6),
            Text(
              'Généralement 2 à 5 secondes.',
              style: DfType.caption.copyWith(fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }
}
