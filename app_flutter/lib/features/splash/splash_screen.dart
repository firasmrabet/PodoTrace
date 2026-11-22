import 'package:flutter/material.dart';

import '../../core/config/app_config.dart';
import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';

/// Écran de démarrage : vérification d'intégrité de la session (JWT).
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  )..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DfScaffoldBackground(
        child: Center(
          child: FadeTransition(
            opacity: CurvedAnimation(parent: _c, curve: Curves.easeOut),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ScaleTransition(
                  scale: Tween(begin: 0.86, end: 1.0).animate(
                    CurvedAnimation(parent: _c, curve: Curves.easeOutBack),
                  ),
                  child: Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: DfGradients.copperSheen,
                      boxShadow: [
                        BoxShadow(
                          color: DfColors.copper.withValues(alpha: 0.35),
                          blurRadius: 42,
                          spreadRadius: 2,
                        ),
                      ],
                    ),
                    child: Center(
                      child: Text(
                        'DF',
                        style: DfType.display.copyWith(
                          color: DfColors.ink,
                          fontSize: 34,
                          letterSpacing: 1,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
                Text(AppConfig.appName, style: DfType.h1),
                const SizedBox(height: 10),
                Text(
                  'TÉLÉSURVEILLANCE DU PIED DIABÉTIQUE',
                  style: DfType.overline.copyWith(letterSpacing: 3.4),
                ),
                const SizedBox(height: 44),
                const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 1.6),
                ),
                const SizedBox(height: 18),
                Text(
                  'Vérification de la session sécurisée…',
                  style: DfType.caption,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
