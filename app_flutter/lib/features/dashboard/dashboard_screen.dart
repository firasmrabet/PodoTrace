import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../data/models/models.dart';
import '../../state/app_state.dart';
import '../analysis/analysis_result_screen.dart';
import '../capture/capture_screen.dart';
import '../chat/chat_screen.dart';
import '../history/history_screen.dart';
import '../map/map_screen.dart';
import '../shell/new_wound_sheet.dart';

/// Tableau de bord « Sentinel » : alerte globale, métriques, actions rapides,
/// plaies actives avec sparklines.
class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<WoundProvider>();
    final stats = state.stats;
    final width = MediaQuery.sizeOf(context).width;

    return RefreshIndicator(
      color: DfColors.copper,
      backgroundColor: DfColors.plumLift,
      onRefresh: () => state.load(silent: true),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(0, 4, 0, 110),
        children: [
          DfContentFrame(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (stats != null)
                  DfAlertBanner(
                    status: stats.globalStatus,
                    message: stats.bannerMessage,
                  ),
                const SizedBox(height: 22),

                // --- Métriques clés -------------------------------------
                _MetricsGrid(stats: stats, wide: width >= 700),
                const SizedBox(height: 26),

                const DfSectionTitle(
                  overline: 'Actions',
                  title: 'Que souhaitez-vous faire ?',
                ),
                const SizedBox(height: 16),
                _QuickActionsGrid(wide: width >= 700),
                const SizedBox(height: 30),

                DfSectionTitle(
                  overline: 'Suivi actif',
                  title: 'Mes plaies',
                  trailing: TextButton.icon(
                    onPressed: () => showModalBottomSheet(
                      context: context,
                      backgroundColor: Colors.transparent,
                      isScrollControlled: true,
                      builder: (_) => const NewWoundSheet(),
                    ),
                    icon: const Icon(Icons.add_rounded, size: 16),
                    label: Text('Ajouter',
                        style: DfType.caption
                            .copyWith(color: DfColors.copperLight)),
                  ),
                ),
                const SizedBox(height: 14),
                if (state.loading && state.wounds.isEmpty)
                  const _LoadingColumn()
                else if (state.wounds.isEmpty)
                  DfGlassCard(
                    child: DfEmptyState(
                      icon: Icons.healing_outlined,
                      title: 'Aucune plaie suivie',
                      message:
                          'Référencez votre première lésion pour démarrer la '
                          'télésurveillance photographique.',
                      action: DfPrimaryButton(
                        label: 'Créer une plaie',
                        icon: Icons.add_rounded,
                        onPressed: () => showModalBottomSheet(
                          context: context,
                          backgroundColor: Colors.transparent,
                          isScrollControlled: true,
                          builder: (_) => const NewWoundSheet(),
                        ),
                      ),
                    ),
                  )
                else
                  for (final wound in state.wounds) ...[
                    _WoundTile(wound: wound),
                    const SizedBox(height: 12),
                  ],
                const SizedBox(height: 24),
                const DfdDisclaimer(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricsGrid extends StatelessWidget {
  const _MetricsGrid({required this.stats, required this.wide});

  final DashboardStats? stats;
  final bool wide;

  @override
  Widget build(BuildContext context) {
    final tiles = [
      DfMetricTile(
        label: 'Plaies actives',
        value: '${stats?.activeWounds ?? 0}',
        footnote: stats?.criticalWounds != null && stats!.criticalWounds > 0
            ? '${stats!.criticalWounds} à risque élevé'
            : 'Toutes sous surveillance',
        trailing: Icon(
          Icons.healing_outlined,
          size: 16,
          color: DfColors.copper.withValues(alpha: 0.7),
        ),
      ),
      DfMetricTile(
        label: 'Dernière surface',
        value: stats?.lastAreaCm2?.toStringAsFixed(2) ?? '—',
        unit: 'cm²',
        footnote: 'Mesure planimétrique calibrée',
        accent: DfColors.copper,
      ),
      DfMetricTile(
        label: 'Évolution',
        value: stats?.trendPct == null
            ? '—'
            : '${stats!.trendPct!.toStringAsFixed(0)} %',
        footnote: stats?.trendPct == null
            ? 'En attente de 2 mesures'
            : (stats!.trendPct! >= 0
                ? 'Réduction depuis la 1ʳᵉ mesure'
                : 'Aggravation à réévaluer'),
        trailing: stats?.trendPct == null
            ? null
            : Icon(
                stats!.trendPct! >= 0
                    ? Icons.trending_down_rounded
                    : Icons.trending_up_rounded,
                size: 16,
                color:
                    stats!.trendPct! >= 0 ? DfColors.stable : DfColors.critical,
              ),
      ),
    ];

    if (wide) {
      return Row(
        children: [
          for (var i = 0; i < tiles.length; i++) ...[
            Expanded(child: tiles[i]),
            if (i < tiles.length - 1) const SizedBox(width: 12),
          ],
        ],
      );
    }
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: tiles[0]),
            const SizedBox(width: 12),
            Expanded(child: tiles[1]),
          ],
        ),
        const SizedBox(height: 12),
        tiles[2],
      ],
    );
  }
}

class _QuickActionsGrid extends StatelessWidget {
  const _QuickActionsGrid({required this.wide});

  final bool wide;

  @override
  Widget build(BuildContext context) {
    final actions = <Widget>[
      DfQuickAction(
        icon: Icons.add_a_photo_outlined,
        label: 'Nouvelle analyse',
        caption: 'Capture guidée + IA',
        highlight: true,
        onTap: () => _launchAnalysis(context),
      ),
      DfQuickAction(
        icon: Icons.timeline_outlined,
        label: 'Historique & courbes',
        caption: 'Trajectoire de cicatrisation',
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
              builder: (_) => const HistoryScreen(embedded: false)),
        ),
      ),
      DfQuickAction(
        icon: Icons.auto_awesome_outlined,
        label: 'Assistant PodoTrace',
        caption: 'Conseils IWGDF',
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const ChatScreen(embedded: false)),
        ),
      ),
      DfQuickAction(
        icon: Icons.local_hospital_outlined,
        label: 'Centres & urgences',
        caption: 'Soins à proximité',
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const MapScreen(embedded: false)),
        ),
      ),
    ];

    if (wide) {
      return Row(
        children: [
          for (var i = 0; i < actions.length; i++) ...[
            Expanded(child: actions[i]),
            if (i < actions.length - 1) const SizedBox(width: 12),
          ],
        ],
      );
    }
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: actions[0]),
            const SizedBox(width: 12),
            Expanded(child: actions[1]),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: actions[2]),
            const SizedBox(width: 12),
            Expanded(child: actions[3]),
          ],
        ),
      ],
    );
  }

  Future<void> _launchAnalysis(BuildContext context) async {
    final wounds = context.read<WoundProvider>();
    if (wounds.wounds.isEmpty) {
      final created = await showModalBottomSheet<bool>(
        context: context,
        backgroundColor: Colors.transparent,
        isScrollControlled: true,
        builder: (_) => const NewWoundSheet(),
      );
      if (created != true || !context.mounted) return;
    }
    final result = await Navigator.of(context).push<AnalysisLaunchResult>(
      MaterialPageRoute(builder: (_) => const CaptureScreen()),
    );
    if (result != null && context.mounted) {
      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => AnalysisResultScreen(result: result)),
      );
    }
  }
}

class _WoundTile extends StatelessWidget {
  const _WoundTile({required this.wound});

  final Wound wound;

  @override
  Widget build(BuildContext context) {
    final color = DfColors.forRisk(wound.latestRiskLevel);
    return DfGlassCard(
      accent: wound.latestRiskLevel == 'high' ? color : null,
      onTap: () {
        context.read<WoundProvider>().select(wound);
        Navigator.of(context).push(
          MaterialPageRoute(
              builder: (_) => const HistoryScreen(embedded: false)),
        );
      },
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(13),
              border: Border.all(color: color.withValues(alpha: 0.35)),
            ),
            child: Icon(Icons.healing_rounded, size: 20, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(wound.label,
                    style: DfType.bodyStrong.copyWith(fontSize: 13.5),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 5),
                Text(
                  '${wound.footSide == 'right' ? 'Pied droit' : 'Pied gauche'} · '
                  '${wound.analysisCount} analyse${wound.analysisCount > 1 ? 's' : ''}'
                  '${wound.wagnerGrade != null ? ' · Wagner ${wound.wagnerGrade}' : ''}',
                  style: DfType.caption.copyWith(fontSize: 10.5),
                ),
              ],
            ),
          ),
          if (wound.sparkline.length >= 2) ...[
            DfSparkline(values: wound.sparkline, width: 62, height: 26),
            const SizedBox(width: 12),
          ],
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                wound.latestAreaCm2 == null
                    ? '—'
                    : wound.latestAreaCm2!.toStringAsFixed(2),
                style: DfType.metricSmall.copyWith(fontSize: 19),
              ),
              Text('cm²', style: DfType.caption.copyWith(fontSize: 9)),
            ],
          ),
          const SizedBox(width: 10),
          DfRiskPill(level: wound.latestRiskLevel),
        ],
      ),
    );
  }
}

class _LoadingColumn extends StatelessWidget {
  const _LoadingColumn();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var i = 0; i < 3; i++)
          DfGlassCard(
            margin: const EdgeInsets.only(bottom: 12),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: DfColors.hairline,
                    borderRadius: BorderRadius.circular(13),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                          height: 12, width: 150, color: DfColors.hairline),
                      const SizedBox(height: 8),
                      Container(height: 9, width: 90, color: DfColors.hairline),
                    ],
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
