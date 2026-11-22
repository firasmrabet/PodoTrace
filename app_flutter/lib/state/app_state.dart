import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../core/storage/secure_store.dart';
import '../data/models/models.dart';
import '../data/services/api_service.dart';

/// Statut de session de l'application.
enum SessionStatus { checking, unauthenticated, pendingOtp, authenticated }

// ---------------------------------------------------------------------------
// Authentification
// ---------------------------------------------------------------------------
class AuthProvider extends ChangeNotifier {
  AuthProvider(this._api);

  final ApiService _api;
  final _store = SecureStore.instance;

  SessionStatus _status = SessionStatus.checking;
  AppUser? _user;
  String? _error;
  String? _pendingEmail;
  String? _devOtp;
  bool _busy = false;

  SessionStatus get status => _status;
  AppUser? get user => _user;
  String? get error => _error;
  String? get pendingEmail => _pendingEmail;
  String? get devOtp => _devOtp;
  bool get busy => _busy;
  bool get isDegradedStorage => _store.isDegraded;

  /// Restaure la session au démarrage (splash screen).
  Future<void> bootstrap() async {
    final token = await _store.read('jwt');
    if (token == null || token.isEmpty) {
      _status = SessionStatus.unauthenticated;
      notifyListeners();
      return;
    }
    _api.token = token;
    try {
      final user = await _api.me();
      _user = user;
      await _store.write('user', jsonEncode(user.toJson()));
      _status = SessionStatus.authenticated;
    } on ApiException catch (e) {
      if (e.isAuthError) {
        await _store.clearSession();
        _api.token = null;
        _status = SessionStatus.unauthenticated;
      } else {
        // Réseau indisponible : on reprend la session en cache (mode dégradé).
        final cached = await _store.read('user');
        if (cached != null) {
          _user = AppUser.fromJson(jsonDecode(cached) as Map<String, dynamic>);
          _status = SessionStatus.authenticated;
        } else {
          _status = SessionStatus.unauthenticated;
        }
      }
    }
    notifyListeners();
  }

  Future<bool> register({
    required String email,
    required String password,
    required String fullName,
    required bool consent,
    String role = 'patient',
    String? specialty,
    String diabetesType = 'none',
    int? birthYear,
  }) async {
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      final r = await _api.register(
        email: email,
        password: password,
        fullName: fullName,
        consentAccepted: consent,
        role: role,
        specialty: specialty,
        diabetesType: diabetesType,
        birthYear: birthYear,
      );
      _pendingEmail = email;
      _devOtp = r.devOtp;
      _status = SessionStatus.pendingOtp;
      return true;
    } on ApiException catch (e) {
      _error = e.message;
      return false;
    } finally {
      _busy = false;
      notifyListeners();
    }
  }

  Future<bool> verifyOtp(String code) async {
    if (_pendingEmail == null) return false;
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      final r = await _api.verifyOtp(email: _pendingEmail!, code: code);
      await _persistSession(r.token, r.user);
      return true;
    } on ApiException catch (e) {
      _error = e.message;
      return false;
    } finally {
      _busy = false;
      notifyListeners();
    }
  }

  Future<bool> login(String email, String password) async {
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      final r = await _api.login(email: email, password: password);
      await _persistSession(r.token, r.user);
      return true;
    } on ApiException catch (e) {
      if (e.needsEmailVerification) {
        _pendingEmail = email;
        _devOtp = e.payload?['dev_otp'] as String?;
        _status = SessionStatus.pendingOtp;
        _error = 'Adresse email non vérifiée : saisissez le code reçu.';
      } else {
        _error = e.message;
      }
      return false;
    } finally {
      _busy = false;
      notifyListeners();
    }
  }

  Future<void> refreshUser() async {
    try {
      _user = await _api.me();
      await _store.write('user', jsonEncode(_user!.toJson()));
      notifyListeners();
    } catch (_) {
      // silencieux : l'UI conserve les données en cache
    }
  }

  Future<void> markOnboardingDone() async {
    if (_user == null) return;
    try {
      _user = await _api.updateProfile({'onboarding_done': true});
      await _store.write('user', jsonEncode(_user!.toJson()));
      notifyListeners();
    } catch (_) {
      // non bloquant
    }
  }

  Future<void> logout() async {
    await _store.clearSession();
    _api.token = null;
    _user = null;
    _status = SessionStatus.unauthenticated;
    _pendingEmail = null;
    notifyListeners();
  }

  Future<void> _persistSession(String token, AppUser user) async {
    _api.token = token;
    _user = user;
    await _store.write('jwt', token);
    await _store.write('user', jsonEncode(user.toJson()));
    _status = SessionStatus.authenticated;
  }
}

// ---------------------------------------------------------------------------
// Plaies & analyses
// ---------------------------------------------------------------------------
class WoundProvider extends ChangeNotifier {
  WoundProvider(this._api);

  final ApiService _api;

  List<Wound> _wounds = [];
  DashboardStats? _stats;
  Wound? _selected;
  TrajectorySummary? _trend;
  List<WoundAnalysis> _analyses = [];
  bool _loading = false;
  String? _error;

  List<Wound> get wounds => _wounds;
  DashboardStats? get stats => _stats;
  Wound? get selected => _selected;
  TrajectorySummary? get trend => _trend;
  List<WoundAnalysis> get analyses => _analyses;
  bool get loading => _loading;
  String? get error => _error;

  Future<void> load({bool silent = false}) async {
    if (!silent) {
      _loading = true;
      notifyListeners();
    }
    try {
      final results = await Future.wait([
        _api.listWounds(),
        _api.dashboard(),
      ]);
      _wounds = results[0] as List<Wound>;
      _stats = results[1] as DashboardStats;
      _error = null;
    } on ApiException catch (e) {
      _error = e.message;
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<Wound?> createWound({
    required String label,
    required String site,
    required String side,
    int? wagner,
  }) async {
    try {
      final wound = await _api.createWound(
        label: label,
        anatomicalSite: site,
        footSide: side,
        wagnerGrade: wagner,
      );
      _wounds = [wound, ..._wounds];
      notifyListeners();
      return wound;
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }

  void select(Wound? wound) {
    _selected = wound;
    notifyListeners();
  }

  Future<void> loadTrend(int woundId) async {
    try {
      _trend = await _api.woundTrend(woundId);
      _analyses = await _api.analysesFor(woundId);
      notifyListeners();
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
    }
  }

  /// Analyse complète d'une image fournie en mémoire (universel Mobile/Web).
  Future<AnalysisResult?> analyse({
    required int woundId,
    required Uint8List imageBytes,
    required String filename,
    double scaleRef = 2.0,
  }) async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      final result = await _api.fullAnalysisBytes(
        woundId: woundId,
        imageBytes: imageBytes,
        filename: filename,
        scaleRef: scaleRef,
      );
      await load(silent: true);
      return result;
    } on ApiException catch (e) {
      _error = e.message;
      return null;
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<Uint8List?> reportPdf(int woundId) async {
    try {
      return await _api.woundReportPdf(woundId);
    } on ApiException catch (e) {
      _error = e.message;
      notifyListeners();
      return null;
    }
  }
}

// ---------------------------------------------------------------------------
// Langue (FR / EN)
// ---------------------------------------------------------------------------
class LocaleProvider extends ChangeNotifier {
  LocaleProvider([this._locale = 'fr']);

  String _locale;
  String get locale => _locale;

  bool get isFrench => _locale == 'fr';

  void toggle() {
    _locale = _locale == 'fr' ? 'en' : 'fr';
    notifyListeners();
  }
}
