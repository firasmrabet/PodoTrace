import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../core/config/app_config.dart';
import '../../core/utils/platform_image.dart' show decodeDataUri;
import '../models/models.dart';

/// Exception métier normalisée (message affichable à l'utilisateur).
class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.code, this.payload});

  final String message;
  final int? statusCode;
  final String? code;
  final Map<String, dynamic>? payload;

  bool get isAuthError => statusCode == 401;
  bool get needsEmailVerification => code == 'email_not_verified';

  @override
  String toString() => message;
}

/// Client HTTP unique de l'application.
///
/// Toutes les opérations sont **multi-plateformes** : les fichiers circulent en
/// `Uint8List` (`MultipartFile.fromBytes`) et jamais via un chemin système,
/// ce qui supprime les erreurs `dart:io` / `File.path` sur Flutter Web.
class ApiService {
  ApiService({Dio? dio})
      : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: AppConfig.apiBase,
                connectTimeout: AppConfig.apiTimeout,
                receiveTimeout: AppConfig.apiTimeout,
                headers: {'Accept': 'application/json'},
              ),
            ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (token != null && token!.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
    if (kDebugMode) {
      _dio.interceptors.add(LogInterceptor(
        request: false,
        requestBody: false,
        responseBody: false,
        logPrint: (o) => debugPrint('[API] $o'),
      ));
    }
  }

  final Dio _dio;
  String? token;

  // ---------------------------------------------------------------------
  // Gestion des erreurs
  // ---------------------------------------------------------------------
  Never _fail(Object error) {
    if (error is DioException) {
      final response = error.response;
      final data = response?.data;
      String message = 'Connexion au serveur impossible. Vérifiez le réseau.';
      String? code;
      Map<String, dynamic>? payload;

      if (data is Map<String, dynamic>) {
        payload = data;
        final detail = data['detail'];
        if (detail is String) {
          message = detail;
        } else if (detail is Map) {
          payload = detail.cast<String, dynamic>();
          message = (detail['message'] as String?) ?? 'Requête refusée.';
          code = detail['code'] as String?;
          final issues = detail['issues'];
          if (issues is List && issues.isNotEmpty) {
            message = '$message\n• ${issues.join('\n• ')}';
          }
        }
      } else if (error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout) {
        message = 'Le serveur met trop de temps à répondre.';
      } else if (error.type == DioExceptionType.connectionError) {
        message = 'Serveur injoignable (${AppConfig.apiBaseUrl}).';
      }
      throw ApiException(
        message,
        statusCode: response?.statusCode,
        code: code,
        payload: payload,
      );
    }
    throw ApiException(error.toString());
  }

  // ---------------------------------------------------------------------
  // Authentification
  // ---------------------------------------------------------------------
  Future<({String token, AppUser user, String? devOtp})> register({
    required String email,
    required String password,
    required String fullName,
    required bool consentAccepted,
    String role = 'patient',
    String? specialty,
    String diabetesType = 'none',
    int? birthYear,
    String locale = 'fr',
  }) async {
    try {
      final r = await _dio.post('/auth/register', data: {
        'email': email,
        'password': password,
        'full_name': fullName,
        'role': role,
        'specialty': specialty,
        'diabetes_type': diabetesType,
        'birth_year': birthYear,
        'locale': locale,
        'consent_accepted': consentAccepted,
      });
      final data = r.data as Map<String, dynamic>;
      return (
        token: '',
        user: _placeholderUser(email, fullName),
        devOtp: data['dev_otp'] as String?
      );
    } catch (e) {
      _fail(e);
    }
  }

  Future<({String token, AppUser user, String? devOtp})> verifyOtp({
    required String email,
    required String code,
  }) async {
    try {
      final r = await _dio
          .post('/auth/verify-otp', data: {'email': email, 'code': code});
      final data = r.data as Map<String, dynamic>;
      token = data['access_token'] as String;
      return (
        token: token!,
        user: AppUser.fromJson(data['user'] as Map<String, dynamic>),
        devOtp: null,
      );
    } catch (e) {
      _fail(e);
    }
  }

  Future<({String token, AppUser user, String? devOtp})> login({
    required String email,
    required String password,
  }) async {
    try {
      final r = await _dio
          .post('/auth/login', data: {'email': email, 'password': password});
      final data = r.data as Map<String, dynamic>;
      token = data['access_token'] as String;
      return (
        token: token!,
        user: AppUser.fromJson(data['user'] as Map<String, dynamic>),
        devOtp: data['dev_otp'] as String?,
      );
    } catch (e) {
      _fail(e);
    }
  }

  Future<({String token, AppUser user})> googleLogin(String idToken) async {
    try {
      final r = await _dio.post('/auth/google', data: {'id_token': idToken});
      final data = r.data as Map<String, dynamic>;
      token = data['access_token'] as String;
      return (
        token: token!,
        user: AppUser.fromJson(data['user'] as Map<String, dynamic>)
      );
    } catch (e) {
      _fail(e);
    }
  }

  Future<AppUser> me() async {
    try {
      final r = await _dio.get('/auth/me');
      return AppUser.fromJson(r.data as Map<String, dynamic>);
    } catch (e) {
      _fail(e);
    }
  }

  Future<AppUser> updateProfile(Map<String, dynamic> patch) async {
    try {
      final r = await _dio.patch('/auth/me', data: patch);
      return AppUser.fromJson(r.data as Map<String, dynamic>);
    } catch (e) {
      _fail(e);
    }
  }

  Future<String?> resendOtp(String email) async {
    try {
      final r = await _dio
          .post('/auth/resend-otp', data: {'email': email, 'code': '000000'});
      return (r.data as Map<String, dynamic>)['dev_otp'] as String?;
    } catch (e) {
      _fail(e);
    }
  }

  // ---------------------------------------------------------------------
  // Plaies & tableau de bord
  // ---------------------------------------------------------------------
  Future<List<Wound>> listWounds({bool includeArchived = false}) async {
    try {
      final r = await _dio.get('/wounds',
          queryParameters: {'include_archived': includeArchived});
      return (r.data as List)
          .map((e) => Wound.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      _fail(e);
    }
  }

  Future<Wound> createWound({
    required String label,
    required String anatomicalSite,
    required String footSide,
    int? wagnerGrade,
  }) async {
    try {
      final r = await _dio.post('/wounds', data: {
        'label': label,
        'anatomical_site': anatomicalSite,
        'foot_side': footSide,
        'wagner_grade': wagnerGrade,
      });
      return Wound.fromJson(r.data as Map<String, dynamic>);
    } catch (e) {
      _fail(e);
    }
  }

  Future<DashboardStats> dashboard() async {
    try {
      final r = await _dio.get('/wounds/dashboard');
      return DashboardStats.fromJson(r.data as Map<String, dynamic>);
    } catch (e) {
      _fail(e);
    }
  }

  Future<TrajectorySummary> woundTrend(int woundId) async {
    try {
      final r = await _dio.get('/wounds/$woundId/trend');
      return TrajectorySummary.fromJson(r.data as Map<String, dynamic>);
    } catch (e) {
      _fail(e);
    }
  }

  Future<List<WoundAnalysis>> analysesFor(int woundId, {int limit = 60}) async {
    try {
      final r = await _dio.get('/analysis', queryParameters: {
        'wound_id': woundId,
        'limit': limit,
      });
      return (r.data as List)
          .map((e) => WoundAnalysis.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      _fail(e);
    }
  }

  // ---------------------------------------------------------------------
  // Analyse IA — upload universel (bytes)
  // ---------------------------------------------------------------------
  Future<AnalysisResult> fullAnalysisBytes({
    required int woundId,
    required Uint8List imageBytes,
    required String filename,
    double scaleRef = AppConfig.defaultScaleRefCm,
    double? manualSegmentPx,
  }) async {
    try {
      final formData = FormData.fromMap({
        'wound_id': woundId,
        'scale_ref': scaleRef,
        if (manualSegmentPx != null) 'manual_segment_px': manualSegmentPx,
        'file': MultipartFile.fromBytes(
          imageBytes,
          filename: filename,
          contentType: DioMediaType('image', 'jpeg'),
        ),
      });

      final r = await _dio.post(
        '/analysis/full-analysis',
        data: formData,
        options: Options(
          receiveTimeout: AppConfig.analysisTimeout,
          sendTimeout: AppConfig.analysisTimeout,
        ),
      );
      final data = r.data as Map<String, dynamic>;
      final images = ((data['images'] as Map?) ?? const {})
          .map((k, v) => MapEntry(k as String, v as String));
      return AnalysisResult(
        analysis:
            WoundAnalysis.fromJson(data['analysis'] as Map<String, dynamic>),
        images: images,
        risk: (data['risk'] as Map?)?.cast<String, dynamic>() ?? const {},
        tissues: (data['tissues'] as Map?)?.cast<String, dynamic>() ?? const {},
        quality: (data['quality'] as Map?)?.cast<String, dynamic>() ?? const {},
        calibration:
            (data['calibration'] as Map?)?.cast<String, dynamic>() ?? const {},
        recommendations:
            ((data['recommendations'] as List?) ?? const []).cast<String>(),
        disclaimer: (data['disclaimer'] as String?) ?? '',
        processingMs: (data['processing_ms'] as int?) ?? 0,
      );
    } catch (e) {
      _fail(e);
    }
  }

  /// Récupère l'image déchiffrée d'une analyse (le backend contrôle l'accès).
  Future<Uint8List> analysisImage(int analysisId,
      {String variant = 'original'}) async {
    try {
      final r = await _dio.get(
        '/analysis/$analysisId/image/$variant',
        options: Options(responseType: ResponseType.bytes),
      );
      return Uint8List.fromList((r.data as List).cast<int>());
    } catch (e) {
      _fail(e);
    }
  }

  Future<WoundAnalysis> reviewAnalysis(
    int analysisId, {
    String? notes,
    String? overrideLevel,
    String? dressing,
    bool validate = true,
  }) async {
    try {
      final r = await _dio.patch('/analysis/$analysisId/review', data: {
        if (notes != null) 'doctor_notes': notes,
        if (overrideLevel != null) 'doctor_override_level': overrideLevel,
        if (dressing != null) 'dressing_prescription': dressing,
        'validate': validate,
      });
      return WoundAnalysis.fromJson(r.data as Map<String, dynamic>);
    } catch (e) {
      _fail(e);
    }
  }

  // ---------------------------------------------------------------------
  // Assistant IA
  // ---------------------------------------------------------------------
  Future<ChatReply> chat({
    required String message,
    int? woundId,
    String locale = 'fr',
  }) async {
    try {
      final r = await _dio.post('/chat',
          data: {
            'message': message,
            'wound_id': woundId,
            'locale': locale,
          },
          options: Options(receiveTimeout: const Duration(seconds: 45)));
      return ChatReply.fromJson(r.data as Map<String, dynamic>);
    } catch (e) {
      _fail(e);
    }
  }

  Future<List<String>> chatSuggestions({String locale = 'fr'}) async {
    try {
      final r = await _dio
          .get('/chat/suggestions', queryParameters: {'locale': locale});
      return ((r.data as Map<String, dynamic>)['suggestions'] as List)
          .cast<String>();
    } catch (_) {
      return const [
        'Ma plaie est-elle infectée ?',
        'Comment décharger mon appui ?',
        'Que signifient mes tissus ?',
      ];
    }
  }

  // ---------------------------------------------------------------------
  // Géolocalisation
  // ---------------------------------------------------------------------
  Future<List<CarePlace>> nearbyPlaces({
    required double lat,
    required double lon,
    double radiusKm = 25,
    String? category,
  }) async {
    try {
      final r = await _dio.get('/geo/nearby', queryParameters: {
        'lat': lat,
        'lon': lon,
        'radius_km': radiusKm,
        if (category != null && category != 'all') 'category': category,
      });
      return ((r.data as Map<String, dynamic>)['places'] as List)
          .map((e) => CarePlace.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      _fail(e);
    }
  }

  // ---------------------------------------------------------------------
  // Rapports
  // ---------------------------------------------------------------------
  Future<Uint8List> woundReportPdf(int woundId) async {
    try {
      final r = await _dio.get(
        '/reports/wound/$woundId/pdf',
        options: Options(
            responseType: ResponseType.bytes,
            receiveTimeout: const Duration(seconds: 60)),
      );
      return Uint8List.fromList((r.data as List).cast<int>());
    } catch (e) {
      _fail(e);
    }
  }

  Future<Map<String, dynamic>> practitionerPatients() async {
    try {
      final r = await _dio.get('/practitioner/patients');
      return r.data as Map<String, dynamic>;
    } catch (e) {
      _fail(e);
    }
  }

  AppUser _placeholderUser(String email, String name) => AppUser(
        id: 0,
        email: email,
        fullName: name,
        role: 'patient',
      );

  /// Utilitaire : première image d'un résultat sous forme d'octets.
  Uint8List? bytesFromDataUri(String? uri) =>
      uri == null ? null : decodeDataUri(uri);
}
