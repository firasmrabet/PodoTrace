import 'package:flutter/material.dart';
import 'package:printing/printing.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../data/models/models.dart';
import '../../state/app_state.dart';

/// Suivi temporel : courbes d'évolution, trajectoire de cicatrisation, PUSH,
/// export du rapport PDF.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key, this.embedded = true, this.initialWoundId});

  final bool embedded;
  final int? initialWoundId;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  int? _woundId;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final state = context.read<WoundProvider>();
      final target = widget.initialWoundId ??
          state.selected?.id ??
          (state.wounds.isNotEmpty ? state.wounds.first.id : null);
      if (target != null) _select(target);
    });
  }

  Future<void> _select(int woundId) async {
    setState(() => _woundId = woundId);
    await context.read<WoundProvider>().loadTrend(woundId);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WoundProvider>();
    final content = _content(state);
    if (widget.embedded) return content;
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
                    Text('Historique & courbes',
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

  Widget _content(WoundProvider state) {
    Wound? wound;
    for (final w in state.wounds) {
      if (w.id == _woundId) {
        wound = w;
        break;
      }
    }
    final trend = state.trend;
    final selectedWoundId = wound?.id;
    return ListView(
      padding: EdgeInsets.fromLTRB(0, 4, 0, widget.embedded ? 110 : 30),
      children: [
        DfContentFrame(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (state.wounds.length > 1)
                SizedBox(
                  height: 38,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: state.wounds.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 8),
                    itemBuilder: (context, i) {
                      final w = state.wounds[i];
                      final selected = w.id == _woundId;
                      return GestureDetector(
                        onTap: () => _select(w.id),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 15, vertical: 9),
                          decoration: BoxDecoration(
                            gradient: selected ? DfGradients.copperSheen : null,
                            color: selected ? null : DfColors.plumSoft,
                            borderRadius: BorderRadius.circular(30),
                            border: Border.all(
                              color: selected
                                  ? Colors.transparent
                                  : DfColors.hairline,
                            ),
                          ),
                          child: Text(
                            w.label,
                            style: DfType.caption.copyWith(
                              color:
                                  selected ? DfColors.ink : DfColors.creamDim,
                              fontWeight: FontWeight.w600,
                              fontSize: 11.5,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              if (state.wounds.length > 1) const SizedBox(height: 18),
              if (wound == null)
                const DfGlassCard(
                  child: DfEmptyState(
                    icon: Icons.healing_outlined,
                    title: 'Aucune plaie sélectionnée',
                    message:
                        'Créez une plaie depuis l\'accueil pour démarrer le suivi.',
                  ),
                )
              else ...[
                DfSectionTitle(
                  overline: 'Trajectoire',
                  title: wound.label,
                  trailing: DfRiskPill(level: wound.latestRiskLevel),
                ),
                const SizedBox(height: 16),
                if (trend != null) ...[
                  DfGlassCard(
                    accent:
                        trend.status == 'worsening' ? DfColors.critical : null,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(trend.label,
                                  style: DfType.h3.copyWith(fontSize: 17)),
                            ),
                            Text(
                              '${trend.reductionPct >= 0 ? '−' : '+'}'
                              '${trend.reductionPct.abs().toStringAsFixed(1)} %',
                              style: DfType.metricSmall.copyWith(
                                fontSize: 22,
                                color: trend.reductionPct >= 0
                                    ? DfColors.stable
                                    : DfColors.critical,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Sur ${trend.weeksFollowed.toStringAsFixed(1)} semaines · '
                          '${trend.rateCm2PerWeek >= 0 ? '' : '+'}'
                          '${trend.rateCm2PerWeek.abs().toStringAsFixed(2)} cm²/semaine · '
                          'PUSH ${trend.pushScore}/17',
                          style: DfType.caption,
                        ),
                        if (trend.alerts.isNotEmpty) ...[
                          const SizedBox(height: 14),
                          for (final alert in trend.alerts)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Icon(Icons.warning_amber_rounded,
                                      size: 14, color: DfColors.moderate),
                                  const SizedBox(width: 9),
                                  Expanded(
                                    child: Text(alert,
                                        style: DfType.caption
                                            .copyWith(height: 1.5)),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                ],
                Builder(builder: (context) {
                  final series = <(String, double, double)>[
                    for (final p in (trend?.series.isNotEmpty == true
                        ? trend!.series
                        : <Map<String, dynamic>>[]))
                      (
                        (p['date'] as String?) ?? '',
                        (p['area_cm2'] as num?)?.toDouble() ?? 0,
                        (p['infection_risk'] as num?)?.toDouble() ?? 0,
                      ),
                    if (trend == null || trend.series.isEmpty)
                      for (final a in state.analyses.reversed)
                        (
                          a.capturedAt.toIso8601String(),
                          a.areaCm2,
                          a.infectionRisk
                        ),
                  ];
                  return DfGlassCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text('ÉVOLUTION DE LA SURFACE',
                                style: DfType.overline.copyWith(fontSize: 9)),
                            const Spacer(),
                            Row(
                              children: [
                                _legendDot(DfColors.copperLight, 'Surface'),
                                const SizedBox(width: 12),
                                _legendDot(DfColors.critical, 'Risque'),
                              ],
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        DfTrendChart(
                          dates: [for (final row in series) _shortDate(row.$1)],
                          areas: [for (final row in series) row.$2],
                          risks: [for (final row in series) row.$3],
                        ),
                      ],
                    ),
                  );
                }),
                const SizedBox(height: 14),
                DfSectionTitle(
                  overline: 'Mesures',
                  title: '${state.analyses.length} analyse(s)',
                ),
                const SizedBox(height: 12),
                for (final a in state.analyses.reversed) ...[
                  _AnalysisRow(analysis: a),
                  const SizedBox(height: 9),
                ],
                const SizedBox(height: 18),
                DfPrimaryButton(
                  label: 'Exporter le rapport PDF',
                  icon: Icons.picture_as_pdf_outlined,
                  expand: true,
                  onPressed: selectedWoundId == null
                      ? null
                      : () => _exportPdf(selectedWoundId),
                ),
                const SizedBox(height: 14),
                const DfdDisclaimer(),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _exportPdf(int woundId) async {
    final bytes = await context.read<WoundProvider>().reportPdf(woundId);
    if (!mounted) return;
    if (bytes == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Aucune analyse à exporter pour le moment.')),
      );
      return;
    }
    await Printing.sharePdf(
        bytes: bytes, filename: 'DiaFoot_Sentinel_rapport.pdf');
  }

  static String _shortDate(String iso) {
    final date = DateTime.tryParse(iso);
    if (date == null) return '—';
    return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}';
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      children: [
        Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(label, style: DfType.caption.copyWith(fontSize: 9)),
      ],
    );
  }
}

class _AnalysisRow extends StatelessWidget {
  const _AnalysisRow({required this.analysis});

  final WoundAnalysis analysis;

  @override
  Widget build(BuildContext context) {
    final color = DfColors.forRisk(analysis.riskLevel);
    final date = analysis.capturedAt;
    return DfGlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
      child: Row(
        children: [
          Container(
            width: 42,
            padding: const EdgeInsets.symmetric(vertical: 7),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: color.withValues(alpha: 0.3)),
            ),
            child: Column(
              children: [
                Text('${date.day}'.padLeft(2, '0'),
                    style: DfType.metricSmall
                        .copyWith(fontSize: 16, color: color)),
                Text(_month(date.month),
                    style: DfType.caption.copyWith(fontSize: 8)),
              ],
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                    '${analysis.areaCm2.toStringAsFixed(2)} cm² · '
                    'P ${analysis.perimeterCm.toStringAsFixed(1)} cm',
                    style: DfType.bodyStrong.copyWith(fontSize: 12.5)),
                const SizedBox(height: 4),
                Text(
                  'Fibrine ${((analysis.composition['fibrin'] ?? 0) * 100).round()} % · '
                  'Granulation ${((analysis.composition['granulation'] ?? 0) * 100).round()} %',
                  style: DfType.caption.copyWith(fontSize: 10),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('${(analysis.infectionRisk * 100).round()} %',
                  style:
                      DfType.bodyStrong.copyWith(fontSize: 13, color: color)),
              Text('infectieux', style: DfType.caption.copyWith(fontSize: 8.5)),
            ],
          ),
          if (analysis.doctorValidated) ...[
            const SizedBox(width: 8),
            const Icon(Icons.verified_rounded,
                size: 15, color: DfColors.stable),
          ],
        ],
      ),
    );
  }

  static String _month(int m) => const [
        'JAN',
        'FÉV',
        'MAR',
        'AVR',
        'MAI',
        'JUI',
        'JUIL',
        'AOÛ',
        'SEP',
        'OCT',
        'NOV',
        'DÉC'
      ][(m - 1).clamp(0, 11)];
}
