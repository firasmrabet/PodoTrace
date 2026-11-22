import 'package:flutter/foundation.dart';

/// Configuration réseau et comportementale de PodoTrace.
///
/// Détection dynamique de l'hôte API :
///   · Web / desktop      → `http://127.0.0.1:8000` (ou `--dart-define=API_BASE_URL=...`)
///   · Émulateur Android  → `http://10.0.2.2:8000`
///   · iOS Simulator      → `http://127.0.0.1:8000`
///   · Appareil physique  → IP LAN ou domaine HTTPS de production
class AppConfig {
  AppConfig._();

  static const String appName = 'PodoTrace';
  static const String version = '1.0.0';
  static const String apiPrefix = '/api/v1';

  /// Surcharge explicite : `flutter run --dart-define=API_BASE_URL=https://api.exemple.com`
  static const String _override = String.fromEnvironment('API_BASE_URL');

  /// Hôte de développement pour l'émulateur Android (10.0.2.2 = hôte local).
  static const String _androidEmulatorHost = 'http://10.0.2.2:8000';

  static String get apiBaseUrl {
    if (_override.isNotEmpty) return _override;
    if (kIsWeb) return 'http://127.0.0.1:8000';
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return _androidEmulatorHost;
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
        return 'http://127.0.0.1:8000';
      default:
        return 'http://127.0.0.1:8000';
    }
  }

  static String get apiBase => '$apiBaseUrl$apiPrefix';

  // --- Contraintes produit ------------------------------------------------
  static const double maxContentWidth = 960;
  static const double clinicalMaxWidth = 900;
  static const double tabletBreakpoint = 768;
  static const Duration apiTimeout = Duration(seconds: 25);
  static const Duration analysisTimeout = Duration(seconds: 90);

  // --- Protocole de capture ----------------------------------------------
  static const double minSharpness = 100;
  static const double minBrightness = 40;
  static const double maxBrightness = 220;
  static const double targetAngleTolerance = 10; // degrés
  static const double defaultScaleRefCm = 2.0; // gommette verte standard
}
