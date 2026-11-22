/// Modèles de données de DiaFoot Sentinel (miroir des schémas Pydantic).
library;

import 'dart:typed_data';

class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    this.specialty,
    this.diabetesType = 'none',
    this.birthYear,
    this.neuropathy = false,
    this.peripheralArteryDisease = false,
    this.emailVerified = false,
    this.consentAccepted = false,
    this.onboardingDone = false,
    this.biometricEnabled = false,
    this.locale = 'fr',
  });

  final int id;
  final String email;
  final String fullName;
  final String role;
  final String? specialty;
  final String diabetesType;
  final int? birthYear;
  final bool neuropathy;
  final bool peripheralArteryDisease;
  final bool emailVerified;
  final bool consentAccepted;
  final bool onboardingDone;
  final bool biometricEnabled;
  final String locale;

  bool get isPractitioner => role == 'practitioner' || role == 'admin';

  String get initials {
    final parts = fullName.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return 'DF';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts.first.substring(0, 1) + parts.last.substring(0, 1))
        .toUpperCase();
  }

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] as int,
        email: json['email'] as String,
        fullName: (json['full_name'] as String?) ?? '',
        role: (json['role'] as String?) ?? 'patient',
        specialty: json['specialty'] as String?,
        diabetesType: (json['diabetes_type'] as String?) ?? 'none',
        birthYear: json['birth_year'] as int?,
        neuropathy: (json['neuropathy'] as bool?) ?? false,
        peripheralArteryDisease:
            (json['peripheral_artery_disease'] as bool?) ?? false,
        emailVerified: (json['email_verified'] as bool?) ?? false,
        consentAccepted: (json['consent_accepted'] as bool?) ?? false,
        onboardingDone: (json['onboarding_done'] as bool?) ?? false,
        biometricEnabled: (json['biometric_enabled'] as bool?) ?? false,
        locale: (json['locale'] as String?) ?? 'fr',
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'full_name': fullName,
        'role': role,
        'specialty': specialty,
        'diabetes_type': diabetesType,
        'birth_year': birthYear,
        'neuropathy': neuropathy,
        'peripheral_artery_disease': peripheralArteryDisease,
        'email_verified': emailVerified,
        'consent_accepted': consentAccepted,
        'onboarding_done': onboardingDone,
        'biometric_enabled': biometricEnabled,
        'locale': locale,
      };
}

class Wound {
  const Wound({
    required this.id,
    required this.label,
    required this.anatomicalSite,
    required this.footSide,
    this.wagnerGrade,
    this.texasClass,
    this.archived = false,
    this.latestAreaCm2,
    this.latestRiskLevel,
    this.latestInfectionRisk,
    this.analysisCount = 0,
    this.trendPct,
    this.sparkline = const [],
  });

  final int id;
  final String label;
  final String anatomicalSite;
  final String footSide;
  final int? wagnerGrade;
  final String? texasClass;
  final bool archived;
  final double? latestAreaCm2;
  final String? latestRiskLevel;
  final double? latestInfectionRisk;
  final int analysisCount;
  final double? trendPct;
  final List<double> sparkline;

  factory Wound.fromJson(Map<String, dynamic> json) => Wound(
        id: json['id'] as int,
        label: (json['label'] as String?) ?? 'Plaie',
        anatomicalSite: (json['anatomical_site'] as String?) ?? '—',
        footSide: (json['foot_side'] as String?) ?? 'right',
        wagnerGrade: json['wagner_grade'] as int?,
        texasClass: json['texas_class'] as String?,
        archived: (json['archived'] as bool?) ?? false,
        latestAreaCm2: (json['latest_area_cm2'] as num?)?.toDouble(),
        latestRiskLevel: json['latest_risk_level'] as String?,
        latestInfectionRisk:
            (json['latest_infection_risk'] as num?)?.toDouble(),
        analysisCount: (json['analysis_count'] as int?) ?? 0,
        trendPct: (json['trend_pct'] as num?)?.toDouble(),
        sparkline: ((json['sparkline'] as List?) ?? const [])
            .map((e) => (e as num).toDouble())
            .toList(),
      );
}

class TissueClass {
  const TissueClass({
    required this.key,
    required this.label,
    required this.color,
    required this.fraction,
  });

  final String key;
  final String label;
  final String color;
  final double fraction;

  factory TissueClass.fromJson(Map<String, dynamic> json) => TissueClass(
        key: json['key'] as String,
        label: json['label'] as String,
        color: json['color'] as String,
        fraction: (json['fraction'] as num).toDouble(),
      );
}

class RiskFactor {
  const RiskFactor({
    required this.code,
    required this.severity,
    required this.label,
    required this.detail,
    this.tissue,
  });

  final String code;
  final String severity; // critical | warning | positive
  final String label;
  final String detail;
  final String? tissue;

  factory RiskFactor.fromJson(Map<String, dynamic> json) => RiskFactor(
        code: (json['code'] as String?) ?? '',
        severity: (json['severity'] as String?) ?? 'warning',
        label: (json['label'] as String?) ?? '',
        detail: (json['detail'] as String?) ?? '',
        tissue: json['tissue'] as String?,
      );
}

class WoundAnalysis {
  const WoundAnalysis({
    required this.id,
    required this.woundId,
    required this.areaCm2,
    required this.perimeterCm,
    required this.infectionRisk,
    required this.ischemiaRisk,
    required this.uncertainty,
    required this.riskLevel,
    required this.composition,
    required this.factors,
    required this.recommendations,
    required this.capturedAt,
    this.pixelsPerCm = 0,
    this.calibrationMethod = 'green_dot',
    this.qualityScore = 1,
    this.pushScore,
    this.engine = '',
    this.doctorNotes,
    this.doctorValidated = false,
    this.doctorOverrideLevel,
    this.explainability = const {},
  });

  final int id;
  final int woundId;
  final double areaCm2;
  final double perimeterCm;
  final double infectionRisk;
  final double ischemiaRisk;
  final double uncertainty;
  final String riskLevel;
  final Map<String, double> composition;
  final List<RiskFactor> factors;
  final List<String> recommendations;
  final DateTime capturedAt;
  final double pixelsPerCm;
  final String calibrationMethod;
  final double qualityScore;
  final int? pushScore;
  final String engine;
  final String? doctorNotes;
  final bool doctorValidated;
  final String? doctorOverrideLevel;
  final Map<String, dynamic> explainability;

  double get globalScore =>
      infectionRisk > ischemiaRisk ? infectionRisk : ischemiaRisk;

  factory WoundAnalysis.fromJson(Map<String, dynamic> json) => WoundAnalysis(
        id: json['id'] as int,
        woundId: json['wound_id'] as int,
        areaCm2: (json['area_cm2'] as num?)?.toDouble() ?? 0,
        perimeterCm: (json['perimeter_cm'] as num?)?.toDouble() ?? 0,
        infectionRisk: (json['infection_risk'] as num?)?.toDouble() ?? 0,
        ischemiaRisk: (json['ischemia_risk'] as num?)?.toDouble() ?? 0,
        uncertainty: (json['uncertainty'] as num?)?.toDouble() ?? 0,
        riskLevel: (json['risk_level'] as String?) ?? 'low',
        composition: ((json['tissue_composition'] as Map?) ?? const {})
            .map((k, v) => MapEntry(k as String, (v as num).toDouble())),
        factors: ((json['risk_factors'] as List?) ?? const [])
            .map((e) => RiskFactor.fromJson(e as Map<String, dynamic>))
            .toList(),
        recommendations: ((json['recommendations'] as List?) ?? const [])
            .map((e) => e as String)
            .toList(),
        capturedAt: DateTime.tryParse((json['captured_at'] as String?) ?? '') ??
            DateTime.now(),
        pixelsPerCm: (json['pixels_per_cm'] as num?)?.toDouble() ?? 0,
        calibrationMethod:
            (json['calibration_method'] as String?) ?? 'green_dot',
        qualityScore: (json['quality_score'] as num?)?.toDouble() ?? 1,
        pushScore: json['push_score'] as int?,
        engine: (json['engine'] as String?) ?? '',
        doctorNotes: json['doctor_notes'] as String?,
        doctorValidated: (json['doctor_validated'] as bool?) ?? false,
        doctorOverrideLevel: json['doctor_override_level'] as String?,
        explainability:
            (json['explainability'] as Map?)?.cast<String, dynamic>() ??
                const {},
      );
}

/// Résultat complet d'une analyse (métriques + rendus visuels).
class AnalysisResult {
  const AnalysisResult({
    required this.analysis,
    required this.images,
    required this.risk,
    required this.tissues,
    required this.quality,
    required this.calibration,
    required this.recommendations,
    required this.disclaimer,
    required this.processingMs,
    this.description = const {},
  });

  final WoundAnalysis analysis;
  final Map<String, String> images;
  final Map<String, dynamic> risk;
  final Map<String, dynamic> tissues;
  final Map<String, dynamic> quality;
  final Map<String, dynamic> calibration;
  final List<String> recommendations;
  final String disclaimer;
  final int processingMs;
  final Map<String, dynamic> description;

  /// Bouton de visualisation → data-URI de l'image correspondante.
  Uint8List? bytesFor(String variant) {
    final uri = images[variant];
    if (uri == null) return null;
    final comma = uri.indexOf(',');
    if (comma < 0) return null;
    try {
      return UriData.parse(uri).contentAsBytes();
    } catch (_) {
      return null;
    }
  }
}

class DashboardStats {
  const DashboardStats({
    required this.activeWounds,
    required this.totalAnalyses,
    required this.globalStatus,
    required this.bannerMessage,
    required this.criticalWounds,
    this.lastAreaCm2,
    this.trendPct,
  });

  final int activeWounds;
  final int totalAnalyses;
  final String globalStatus;
  final String bannerMessage;
  final int criticalWounds;
  final double? lastAreaCm2;
  final double? trendPct;

  factory DashboardStats.fromJson(Map<String, dynamic> json) => DashboardStats(
        activeWounds: (json['active_wounds'] as int?) ?? 0,
        totalAnalyses: (json['total_analyses'] as int?) ?? 0,
        globalStatus: (json['global_status'] as String?) ?? 'no_data',
        bannerMessage: (json['banner_message'] as String?) ?? '',
        criticalWounds: (json['critical_wounds'] as int?) ?? 0,
        lastAreaCm2: (json['last_area_cm2'] as num?)?.toDouble(),
        trendPct: (json['trend_pct'] as num?)?.toDouble(),
      );
}

class ChatReply {
  const ChatReply({
    required this.reply,
    required this.redFlag,
    required this.sources,
    required this.provider,
    this.emergencyMessage,
    this.redFlagTerms = const [],
    this.suggestions = const [],
  });

  final String reply;
  final bool redFlag;
  final List<String> sources;
  final String provider;
  final String? emergencyMessage;
  final List<String> redFlagTerms;
  final List<String> suggestions;

  factory ChatReply.fromJson(Map<String, dynamic> json) => ChatReply(
        reply: (json['reply'] as String?) ?? '',
        redFlag: (json['red_flag'] as bool?) ?? false,
        sources: ((json['sources'] as List?) ?? const []).cast<String>(),
        provider: (json['provider'] as String?) ?? 'heuristic',
        emergencyMessage: json['emergency_message'] as String?,
        redFlagTerms:
            ((json['red_flag_terms'] as List?) ?? const []).cast<String>(),
        suggestions:
            ((json['suggestions'] as List?) ?? const []).cast<String>(),
      );
}

class ChatEntry {
  ChatEntry({
    required this.text,
    required this.isUser,
    this.redFlag = false,
    this.sources = const [],
    this.pending = false,
  });

  final String text;
  final bool isUser;
  final bool redFlag;
  final List<String> sources;
  bool pending;
}

class CarePlace {
  const CarePlace({
    required this.id,
    required this.name,
    required this.category,
    required this.categoryLabel,
    required this.lat,
    required this.lon,
    required this.distanceKm,
    this.address,
    this.phone,
    this.openingHours,
    this.emergency247 = false,
  });

  final String id;
  final String name;
  final String category;
  final String categoryLabel;
  final double lat;
  final double lon;
  final double distanceKm;
  final String? address;
  final String? phone;
  final String? openingHours;
  final bool emergency247;

  factory CarePlace.fromJson(Map<String, dynamic> json) => CarePlace(
        id: json['id'] as String,
        name: json['name'] as String,
        category: (json['category'] as String?) ?? 'clinic',
        categoryLabel: (json['category_label'] as String?) ?? '',
        lat: (json['lat'] as num).toDouble(),
        lon: (json['lon'] as num).toDouble(),
        distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
        address: json['address'] as String?,
        phone: json['phone'] as String?,
        openingHours: json['opening_hours'] as String?,
        emergency247: (json['emergency_24_7'] as bool?) ?? false,
      );
}

class TrajectorySummary {
  const TrajectorySummary({
    required this.status,
    required this.label,
    required this.reductionPct,
    required this.weeksFollowed,
    required this.rateCm2PerWeek,
    required this.pushScore,
    required this.alerts,
    required this.series,
  });

  final String status;
  final String label;
  final double reductionPct;
  final double weeksFollowed;
  final double rateCm2PerWeek;
  final int pushScore;
  final List<String> alerts;
  final List<Map<String, dynamic>> series;

  factory TrajectorySummary.fromJson(Map<String, dynamic> json) =>
      TrajectorySummary(
        status: (json['status'] as String?) ?? 'staged',
        label: (json['label'] as String?) ?? '',
        reductionPct: (json['reduction_pct'] as num?)?.toDouble() ?? 0,
        weeksFollowed: (json['weeks_followed'] as num?)?.toDouble() ?? 0,
        rateCm2PerWeek: (json['rate_cm2_per_week'] as num?)?.toDouble() ?? 0,
        pushScore: (json['push_score'] as int?) ?? 0,
        alerts: ((json['alerts'] as List?) ?? const []).cast<String>(),
        series: ((json['series'] as List?) ?? const [])
            .map((e) => (e as Map).cast<String, dynamic>())
            .toList(),
      );
}
