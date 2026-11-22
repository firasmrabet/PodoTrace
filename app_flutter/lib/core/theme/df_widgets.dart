import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../theme/df_theme.dart';

// ---------------------------------------------------------------------------
// Fond & texture
// ---------------------------------------------------------------------------

/// Fond « Bio-Luxe » : voile prune, halo cuivré, grain de papier discret.
class DfScaffoldBackground extends StatelessWidget {
  const DfScaffoldBackground(
      {super.key, required this.child, this.aurora = true});

  final Widget child;
  final bool aurora;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        const Positioned.fill(
          child: DecoratedBox(
              decoration: BoxDecoration(gradient: DfGradients.plumVeil)),
        ),
        if (aurora)
          const Positioned.fill(
            child: IgnorePointer(
              child: DecoratedBox(
                  decoration: BoxDecoration(gradient: DfGradients.aurora)),
            ),
          ),
        Positioned.fill(
          child: IgnorePointer(
            child: CustomPaint(painter: _GrainPainter()),
          ),
        ),
        Positioned.fill(child: child),
      ],
    );
  }
}

class _GrainPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    // Texture volontairement neutre : le système « Sérénité » est mat,
    // sans grain ni halo (direction artistique précédente abandonnée).
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ---------------------------------------------------------------------------
// Verre & surface
// ---------------------------------------------------------------------------

/// Carte en verre dépoli avec filet cuivré et ombre profonde.
class DfGlassCard extends StatelessWidget {
  const DfGlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.margin,
    this.onTap,
    this.accent,
    this.blur = 18,
    this.borderRadius = 20,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final VoidCallback? onTap;
  final Color? accent;
  final double blur;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(borderRadius);
    return Padding(
      padding: margin ?? EdgeInsets.zero,
      child: ClipRRect(
        borderRadius: radius,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: DfColors.plum,
            borderRadius: radius,
            border: Border.all(
              color: accent?.withValues(alpha: 0.45) ?? DfColors.hairline,
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: DfColors.cream.withValues(alpha: 0.05),
                blurRadius: 26,
                offset: const Offset(0, 10),
              ),
              if (accent != null)
                BoxShadow(
                  color: accent!.withValues(alpha: 0.10),
                  blurRadius: 34,
                  spreadRadius: -8,
                ),
            ],
          ),
          child: InkWell(
            onTap: onTap,
            splashColor: DfColors.copper.withValues(alpha: 0.08),
            highlightColor: Colors.transparent,
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
  }
}

class DfHairline extends StatelessWidget {
  const DfHairline({super.key, this.width, this.color});

  final double? width;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 0.8,
      width: width,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            (color ?? DfColors.copper).withValues(alpha: 0),
            (color ?? DfColors.copper).withValues(alpha: 0.55),
            (color ?? DfColors.copper).withValues(alpha: 0),
          ],
        ),
      ),
    );
  }
}

/// Titre de section : surtitre cuivré + serif éditorial.
class DfSectionTitle extends StatelessWidget {
  const DfSectionTitle({
    super.key,
    required this.overline,
    required this.title,
    this.trailing,
  });

  final String overline;
  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(overline.toUpperCase(), style: DfType.overline),
              const SizedBox(height: 6),
              Text(title, style: DfType.h1),
            ],
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Boutons
// ---------------------------------------------------------------------------

/// Bouton principal cuivré à pulsation douce (action prioritaire unique).
class DfPrimaryButton extends StatefulWidget {
  const DfPrimaryButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.pulse = false,
    this.expand = false,
    this.loading = false,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool pulse;
  final bool expand;
  final bool loading;

  @override
  State<DfPrimaryButton> createState() => _DfPrimaryButtonState();
}

class _DfPrimaryButtonState extends State<DfPrimaryButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final inner = Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 26),
      decoration: BoxDecoration(
        gradient: DfGradients.copperSheen,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: DfColors.copper.withValues(alpha: 0.34),
            blurRadius: 24,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (widget.loading)
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation(DfColors.ink),
              ),
            )
          else if (widget.icon != null)
            Icon(widget.icon, size: 19, color: DfColors.ink),
          if (widget.icon != null || widget.loading) const SizedBox(width: 10),
          Text(
            widget.label,
            style: DfType.bodyStrong.copyWith(
              color: DfColors.ink,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );

    final button = Opacity(
      opacity: widget.onPressed == null ? 0.45 : 1,
      child: GestureDetector(
        onTap: widget.onPressed,
        child: widget.pulse
            ? AnimatedBuilder(
                animation: _c,
                builder: (context, child) {
                  final t = Curves.easeInOut.transform(_c.value);
                  return Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(
                          color: DfColors.copper
                              .withValues(alpha: 0.10 + 0.18 * t),
                          blurRadius: 18 + 18 * t,
                          spreadRadius: 1 + 3 * t,
                        ),
                      ],
                    ),
                    child: child,
                  );
                },
                child: inner,
              )
            : inner,
      ),
    );

    return widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }
}

class DfGhostButton extends StatelessWidget {
  const DfGhostButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.danger = false,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final color = danger ? DfColors.critical : DfColors.copperDeep;
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: icon == null
          ? const SizedBox.shrink()
          : Icon(icon, size: 17, color: color),
      label: Text(label,
          style: DfType.caption.copyWith(color: color, fontSize: 12.5)),
      style: OutlinedButton.styleFrom(
        side: BorderSide(color: color.withValues(alpha: 0.35)),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Indicateurs cliniques
// ---------------------------------------------------------------------------

/// Pastille de risque : couleur + libellé (jamais la couleur seule).
class DfRiskPill extends StatelessWidget {
  const DfRiskPill({super.key, required this.level, this.label});

  final String? level;
  final String? label;

  static const _labels = {
    'low': 'Faible',
    'moderate': 'Modéré',
    'high': 'Élevé'
  };

  @override
  Widget build(BuildContext context) {
    final color = DfColors.forRisk(level);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(30),
        border: Border.all(color: color.withValues(alpha: 0.45)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 7),
          Text(
            label ?? _labels[level] ?? '—',
            style: DfType.caption.copyWith(
              color: color,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }
}

/// Jauge circulaire animée du risque global (0 → 1).
class DfRiskGauge extends StatelessWidget {
  const DfRiskGauge({
    super.key,
    required this.value,
    required this.level,
    this.size = 150,
    this.caption = 'Risque global',
  });

  final double value;
  final String level;
  final double size;
  final String caption;

  @override
  Widget build(BuildContext context) {
    final color = DfColors.forRisk(level);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.clamp(0, 1)),
      duration: const Duration(milliseconds: 1100),
      curve: Curves.easeOutCubic,
      builder: (context, v, _) {
        return SizedBox(
          width: size,
          height: size,
          child: CustomPaint(
            painter: _GaugePainter(value: v, color: color),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('${(v * 100).round()}',
                      style: DfType.metric.copyWith(fontSize: size * 0.26)),
                  Text('%', style: DfType.caption),
                  const SizedBox(height: 2),
                  Text(
                    caption,
                    textAlign: TextAlign.center,
                    style: DfType.caption.copyWith(fontSize: 9.5),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _GaugePainter extends CustomPainter {
  _GaugePainter({required this.value, required this.color});

  final double value;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromCircle(
        center: size.center(Offset.zero), radius: size.width / 2 - 6);
    const start = math.pi * 0.75;
    const sweep = math.pi * 1.5;

    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 7
      ..strokeCap = StrokeCap.round
      ..color = DfColors.hairline;
    canvas.drawArc(rect, start, sweep, false, track);

    final progress = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 7
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        startAngle: start,
        endAngle: start + sweep,
        colors: [color.withValues(alpha: 0.35), color],
      ).createShader(rect);
    canvas.drawArc(rect, start, sweep * value, false, progress);

    // Graduations cliniques (35 % = modéré, 65 % = élevé)
    final tick = Paint()
      ..color = DfColors.muted.withValues(alpha: 0.5)
      ..strokeWidth = 1.2;
    for (final t in [0.35, 0.65]) {
      final a = start + sweep * t;
      final center = size.center(Offset.zero);
      final r1 = size.width / 2 - 14;
      final r2 = size.width / 2 - 2;
      canvas.drawLine(
        center + Offset(math.cos(a) * r1, math.sin(a) * r1),
        center + Offset(math.cos(a) * r2, math.sin(a) * r2),
        tick,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _GaugePainter old) =>
      old.value != value || old.color != color;
}

/// Diagramme circulaire (donut) de composition tissulaire, légende interactive.
class DfTissueDonut extends StatelessWidget {
  const DfTissueDonut({
    super.key,
    required this.composition,
    this.size = 168,
    this.selected,
    this.onSelect,
  });

  final Map<String, double> composition;
  final double size;
  final String? selected;
  final ValueChanged<String?>? onSelect;

  static const _meta = <String, (String, Color)>{
    'granulation': ('Granulation', DfColors.tissueGranulation),
    'fibrin': ('Fibrine / Slough', DfColors.tissueFibrin),
    'necrosis': ('Nécrose', DfColors.tissueNecrosis),
    'epithelial': ('Épithélialisation', DfColors.tissueEpithelial),
  };

  @override
  Widget build(BuildContext context) {
    final entries = _meta.entries
        .where((e) => (composition[e.key] ?? 0) > 0)
        .toList(growable: false);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 900),
          curve: Curves.easeOutCubic,
          builder: (context, t, _) => SizedBox(
            width: size,
            height: size,
            child: CustomPaint(
              painter: _DonutPainter(
                composition: composition,
                progress: t,
                selected: selected,
              ),
            ),
          ),
        ),
        const SizedBox(width: 22),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final e in entries)
                _LegendRow(
                  label: _meta[e.key]!.$1,
                  color: _meta[e.key]!.$2,
                  value: composition[e.key] ?? 0,
                  dimmed: selected != null && selected != e.key,
                  onTap: () => onSelect?.call(selected == e.key ? null : e.key),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _LegendRow extends StatelessWidget {
  const _LegendRow({
    required this.label,
    required this.color,
    required this.value,
    required this.onTap,
    this.dimmed = false,
  });

  final String label;
  final Color color;
  final double value;
  final VoidCallback onTap;
  final bool dimmed;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Opacity(
        opacity: dimmed ? 0.35 : 1,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: [
              Container(
                width: 9,
                height: 9,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 10),
              Expanded(
                  child: Text(label,
                      style: DfType.caption.copyWith(fontSize: 12))),
              Text(
                '${(value * 100).round()} %',
                style: DfType.bodyStrong.copyWith(fontSize: 12.5, color: color),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DonutPainter extends CustomPainter {
  _DonutPainter(
      {required this.composition, required this.progress, this.selected});

  final Map<String, double> composition;
  final double progress;
  final String? selected;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.width / 2 - 8;
    final rect = Rect.fromCircle(center: center, radius: radius);
    final stroke = radius * 0.42;

    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..color = DfColors.hairline,
    );

    var angle = -math.pi / 2;
    for (final entry in DfTissueDonut._meta.entries) {
      final v = composition[entry.key] ?? 0;
      if (v <= 0) continue;
      final sweep = 2 * math.pi * v * progress;
      final isSel = selected == entry.key;
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = isSel ? stroke * 1.18 : stroke
        ..strokeCap = StrokeCap.butt
        ..color = selected == null || isSel
            ? entry.value.$2
            : entry.value.$2.withValues(alpha: 0.35);
      canvas.drawArc(rect, angle, sweep, false, paint);
      angle += 2 * math.pi * v * progress;
    }
  }

  @override
  bool shouldRepaint(covariant _DonutPainter old) =>
      old.progress != progress || old.selected != selected;
}

/// Sparkline de surface (mini-courbe d'évolution).
class DfSparkline extends StatelessWidget {
  const DfSparkline({
    super.key,
    required this.values,
    this.width = 86,
    this.height = 32,
    this.color,
  });

  final List<double> values;
  final double width;
  final double height;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    if (values.length < 2) {
      return SizedBox(
        width: width,
        height: height,
        child: Center(child: Text('—', style: DfType.caption)),
      );
    }
    final minV = values.reduce(math.min);
    final maxV = values.reduce(math.max);
    final span = (maxV - minV).abs() < 1e-6 ? 1.0 : maxV - minV;
    // Une surface qui diminue est une bonne nouvelle → couleur stable.
    final improving = values.last < values.first;
    final stroke = color ?? (improving ? DfColors.stable : DfColors.moderate);

    return SizedBox(
      width: width,
      height: height,
      child: CustomPaint(
        painter: _SparkPainter(
            values: values, minV: minV, span: span, color: stroke),
      ),
    );
  }
}

class _SparkPainter extends CustomPainter {
  _SparkPainter({
    required this.values,
    required this.minV,
    required this.span,
    required this.color,
  });

  final List<double> values;
  final double minV;
  final double span;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const pad = 3.0;
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = pad + (size.width - 2 * pad) * i / (values.length - 1);
      final y = size.height -
          pad -
          (size.height - 2 * pad) * ((values[i] - minV) / span);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.8
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..color = color,
    );
    final last = path.getBounds().bottomRight;
    canvas.drawCircle(last, 2.4, Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant _SparkPainter old) => old.values != values;
}

/// Tuile de statistique clé.
class DfMetricTile extends StatelessWidget {
  const DfMetricTile({
    super.key,
    required this.label,
    required this.value,
    this.unit,
    this.footnote,
    this.trailing,
    this.accent,
  });

  final String label;
  final String value;
  final String? unit;
  final String? footnote;
  final Widget? trailing;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    return DfGlassCard(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      accent: accent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(label.toUpperCase(),
                    style: DfType.overline.copyWith(fontSize: 9)),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Flexible(
                child: Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: DfType.metric.copyWith(fontSize: 30),
                ),
              ),
              if (unit != null) ...[
                const SizedBox(width: 5),
                Text(unit!, style: DfType.caption.copyWith(fontSize: 12)),
              ],
            ],
          ),
          if (footnote != null) ...[
            const SizedBox(height: 6),
            Text(footnote!, style: DfType.caption.copyWith(fontSize: 10.5)),
          ],
        ],
      ),
    );
  }
}

/// Bandeau d'alerte contextuel (état global du suivi).
class DfAlertBanner extends StatelessWidget {
  const DfAlertBanner({
    super.key,
    required this.status,
    required this.message,
    this.onTap,
  });

  final String status;
  final String message;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = DfColors.forStatus(status);
    final icon = switch (status) {
      'alert' => Icons.warning_amber_rounded,
      'improving' => Icons.trending_down_rounded,
      'stable' => Icons.shield_outlined,
      _ => Icons.info_outline_rounded,
    };
    return DfGlassCard(
      accent: color,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      onTap: onTap,
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.14),
              shape: BoxShape.circle,
              border: Border.all(color: color.withValues(alpha: 0.4)),
            ),
            child: Icon(icon, size: 19, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  switch (status) {
                    'alert' => 'ALERTE CLINIQUE',
                    'improving' => 'AMÉLIORATION',
                    'stable' => 'ÉTAT STABLE',
                    _ => 'PREMIÈRE ANALYSE',
                  },
                  style: DfType.overline.copyWith(color: color, fontSize: 9),
                ),
                const SizedBox(height: 5),
                Text(message, style: DfType.body.copyWith(fontSize: 13)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Encart de décharge médicale réglementaire.
class DfdDisclaimer extends StatelessWidget {
  const DfdDisclaimer({super.key, this.compact = false});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.gavel_rounded,
            size: 13, color: DfColors.muted.withValues(alpha: 0.8)),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            compact
                ? 'Outil d\'aide en phase de validation — ne remplace pas un avis médical.'
                : 'PodoTrace est un outil d\'aide à la télésurveillance en phase de validation clinique. '
                    'Les résultats ne constituent ni un diagnostic ni une prescription. '
                    'En cas de fièvre, de douleur brutale ou d\'extension rapide de la rougeur, '
                    'contactez immédiatement les urgences (15 / 190).',
            style: DfType.caption
                .copyWith(fontSize: compact ? 10 : 10.5, height: 1.5),
          ),
        ),
      ],
    );
  }
}

/// État vide élégant.
class DfEmptyState extends StatelessWidget {
  const DfEmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 66,
              height: 66,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: DfColors.copper.withValues(alpha: 0.08),
                border: Border.all(color: DfColors.hairline),
              ),
              child: Icon(icon, color: DfColors.copperLight, size: 27),
            ),
            const SizedBox(height: 20),
            Text(title, style: DfType.h2, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(message, style: DfType.caption, textAlign: TextAlign.center),
            if (action != null) ...[const SizedBox(height: 22), action!],
          ],
        ),
      ),
    );
  }
}

/// Cadre de largeur clinique maximale (lisibilité sur tablette / desktop).
class DfContentFrame extends StatelessWidget {
  const DfContentFrame({
    super.key,
    required this.child,
    this.maxWidth = 900,
    this.padding = const EdgeInsets.fromLTRB(20, 8, 20, 28),
  });

  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: Padding(padding: padding, child: child),
      ),
    );
  }
}

/// Carte d'action rapide (dashboard).
class DfQuickAction extends StatelessWidget {
  const DfQuickAction({
    super.key,
    required this.icon,
    required this.label,
    this.caption,
    this.onTap,
    this.highlight = false,
  });

  final IconData icon;
  final String label;
  final String? caption;
  final VoidCallback? onTap;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    return DfGlassCard(
      onTap: onTap,
      accent: highlight ? DfColors.copper : null,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            icon,
            size: 22,
            color: highlight ? DfColors.copperLight : DfColors.creamDim,
          ),
          const SizedBox(height: 14),
          Text(label, style: DfType.bodyStrong.copyWith(fontSize: 13)),
          if (caption != null) ...[
            const SizedBox(height: 4),
            Text(caption!, style: DfType.caption.copyWith(fontSize: 10.5)),
          ],
        ],
      ),
    );
  }
}

/// Sélecteur segmenté stylisé (onglets de visualisation).
class DfSegmentedTabs extends StatelessWidget {
  const DfSegmentedTabs({
    super.key,
    required this.tabs,
    required this.value,
    required this.onChanged,
  });

  final List<String> tabs;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return DfGlassCard(
      padding: const EdgeInsets.all(5),
      borderRadius: 14,
      child: Row(
        children: [
          for (final tab in tabs)
            Expanded(
              child: GestureDetector(
                onTap: () => onChanged(tab),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  padding: const EdgeInsets.symmetric(vertical: 11),
                  decoration: BoxDecoration(
                    gradient: tab == value ? DfGradients.copperSheen : null,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Center(
                    child: Text(
                      tab,
                      textAlign: TextAlign.center,
                      style: DfType.caption.copyWith(
                        fontSize: 11,
                        fontWeight:
                            tab == value ? FontWeight.w700 : FontWeight.w500,
                        color: tab == value ? DfColors.ink : DfColors.creamDim,
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Petit graphique linéaire (fl_chart) pour l'historique.
class DfTrendChart extends StatelessWidget {
  const DfTrendChart({
    super.key,
    required this.dates,
    required this.areas,
    required this.risks,
    this.height = 240,
  });

  final List<String> dates;
  final List<double> areas;
  final List<double> risks;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (areas.length < 2) {
      return SizedBox(
        height: height,
        child: const DfEmptyState(
          icon: Icons.show_chart_rounded,
          title: 'Pas encore de courbe',
          message:
              'Deux analyses minimum sont nécessaires pour tracer l\'évolution.',
        ),
      );
    }
    final maxArea = areas.reduce(math.max) * 1.15;
    final spots = <FlSpot>[
      for (var i = 0; i < areas.length; i++) FlSpot(i.toDouble(), areas[i]),
    ];
    final riskSpots = <FlSpot>[
      for (var i = 0; i < risks.length; i++)
        FlSpot(i.toDouble(), risks[i] * maxArea),
    ];

    return SizedBox(
      height: height,
      child: LineChart(
        LineChartData(
          minY: 0,
          maxY: maxArea,
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: maxArea / 4,
            getDrawingHorizontalLine: (_) => const FlLine(
              color: DfColors.hairline,
              strokeWidth: 0.6,
            ),
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            topTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles:
                const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 38,
                getTitlesWidget: (v, _) => Text(
                  v.toStringAsFixed(0),
                  style: DfType.caption.copyWith(fontSize: 9),
                ),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 26,
                interval: 1,
                getTitlesWidget: (v, _) {
                  final i = v.round();
                  if (i < 0 || i >= dates.length) {
                    return const SizedBox.shrink();
                  }
                  return Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(dates[i],
                        style: DfType.caption.copyWith(fontSize: 9)),
                  );
                },
              ),
            ),
          ),
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipColor: (_) => DfColors.plumLift,
              getTooltipItems: (spots) => spots
                  .map((s) => LineTooltipItem(
                        '${s.y.toStringAsFixed(2)} cm²',
                        DfType.caption.copyWith(color: DfColors.cream),
                      ))
                  .toList(),
            ),
          ),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              curveSmoothness: 0.3,
              barWidth: 2.6,
              color: DfColors.copperLight,
              dotData: FlDotData(
                show: true,
                getDotPainter: (_, __, ___, ____) => FlDotCirclePainter(
                  radius: 3.4,
                  color: DfColors.copperLight,
                  strokeColor: DfColors.ink,
                  strokeWidth: 1.4,
                ),
              ),
              belowBarData: BarAreaData(
                show: true,
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    DfColors.copper.withValues(alpha: 0.28),
                    DfColors.copper.withValues(alpha: 0.0),
                  ],
                ),
              ),
            ),
            LineChartBarData(
              spots: riskSpots,
              isCurved: true,
              curveSmoothness: 0.3,
              barWidth: 1.6,
              color: DfColors.critical.withValues(alpha: 0.75),
              dashArray: const [5, 4],
              dotData: const FlDotData(show: false),
            ),
          ],
        ),
      ),
    );
  }
}
