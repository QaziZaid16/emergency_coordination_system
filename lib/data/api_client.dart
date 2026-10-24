import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

class ApiSession {
  ApiSession({
    required this.token,
    required this.expiresAt,
    required this.sessionExpiresAt,
    required this.user,
    required this.rememberMe,
    this.refreshToken,
  });
  String token;
  DateTime expiresAt;
  DateTime sessionExpiresAt;
  String? refreshToken;
  final Map<String, dynamic> user;
  final bool rememberMe;
  String get role => user['role'] as String;
}

abstract interface class ApiSessionStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class SecureApiSessionStorage implements ApiSessionStorage {
  const SecureApiSessionStorage(this.storage);
  final FlutterSecureStorage storage;

  @override
  Future<String?> read(String key) => storage.read(key: key);
  @override
  Future<void> write(String key, String value) =>
      storage.write(key: key, value: value);
  @override
  Future<void> delete(String key) => storage.delete(key: key);
}

class ApiClient {
  ApiClient({String? baseUrl, http.Client? client, ApiSessionStorage? storage})
    : baseUrl = (baseUrl ?? const String.fromEnvironment('API_BASE_URL'))
          .replaceAll(RegExp(r'/$'), ''),
      _http = client ?? http.Client(),
      _storage =
          storage ?? const SecureApiSessionStorage(FlutterSecureStorage());

  final String baseUrl;
  final http.Client _http;
  final ApiSessionStorage _storage;
  final sessionExpired = ValueNotifier<bool>(false);
  Future<void>? _refreshing;
  static const _sessionKey = 'coordination_api_session_v2';
  static const _legacySessionKey = 'coordination_api_session_v1';

  bool get configured =>
      baseUrl.startsWith('https://') || baseUrl.startsWith('http://');

  Future<ApiSession?> restoreSession() async {
    // Earlier builds persisted every login without asking. Drop that legacy
    // session so upgrading cannot silently enable Remember Me.
    await _storage.delete(_legacySessionKey);
    final raw = await _storage.read(_sessionKey);
    if (raw == null) return null;
    late final ApiSession session;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      session = ApiSession(
        token: map['token'] as String,
        expiresAt: DateTime.parse(map['expires_at'] as String),
        sessionExpiresAt: DateTime.parse(map['session_expires_at'] as String),
        refreshToken: map['refresh_token'] as String?,
        user: Map<String, dynamic>.from(map['user'] as Map),
        rememberMe: map['remember_me'] as bool? ?? false,
      );
    } catch (_) {
      await clearStoredSession();
      return null;
    }
    if (!session.rememberMe ||
        session.refreshToken == null ||
        !session.sessionExpiresAt.isAfter(DateTime.now().toUtc()) ||
        !{'super_admin', 'admin', 'user', 'responder'}.contains(session.role)) {
      await clearStoredSession();
      return null;
    }
    try {
      await _ensureFreshSession(session);
      final currentUser = await get('/auth/me', session);
      if (currentUser['id'] != session.user['id'] ||
          currentUser['role'] != session.role) {
        await clearStoredSession();
        return null;
      }
      return ApiSession(
        token: session.token,
        expiresAt: session.expiresAt,
        sessionExpiresAt: session.sessionExpiresAt,
        refreshToken: session.refreshToken,
        user: currentUser,
        rememberMe: true,
      );
    } on ApiException catch (e) {
      if (e.statusCode == 401 || e.statusCode == 403) {
        await clearStoredSession();
        return null;
      }
      // Keep the protected session in secure storage for retry, but never
      // present a dashboard until the server validates it again.
      rethrow;
    } catch (_) {
      throw const ApiException(
        'Could not verify the saved session. Try again.',
      );
    }
  }

  Future<ApiSession> login(
    String email,
    String password,
    String portal,
    {required bool rememberMe}) async {
    await _revokeStoredSession();
    sessionExpired.value = false;
    final json = await _request(
      'POST',
      '/auth/login',
      body: {
        'email': email.trim(),
        'password': password,
        'remember_me': rememberMe,
      },
    );
    return _saveSession(json, rememberMe: rememberMe);
  }

  Future<ApiSession> registerUser(
    String name,
    String email,
    String password, {
    required bool rememberMe,
  }) async {
    await _revokeStoredSession();
    sessionExpired.value = false;
    final json = await _request(
      'POST',
      '/auth/register',
      body: {
        'display_name': name.trim(),
        'email': email.trim(),
        'password': password,
        'remember_me': rememberMe,
      },
    );
    return _saveSession(json, rememberMe: rememberMe);
  }

  Future<ApiSession> _saveSession(
    Map<String, dynamic> json, {
    required bool rememberMe,
  }) async {
    final refreshToken = json['refresh_token'] as String?;
    if (rememberMe && refreshToken == null) {
      throw const ApiException(
        'The service does not support a secure remembered session. Update the backend and try again.',
      );
    }
    final expiresAt = DateTime.parse(json['expires_at'] as String).toUtc();
    final session = ApiSession(
      token: json['access_token'] as String,
      expiresAt: expiresAt,
      sessionExpiresAt: DateTime.parse(
        (json['session_expires_at'] as String?) ?? json['expires_at'] as String,
      ).toUtc(),
      refreshToken: refreshToken,
      user: Map<String, dynamic>.from(json['user'] as Map),
      rememberMe: rememberMe,
    );
    if (rememberMe) {
      await _storage.write(
        _sessionKey,
        jsonEncode({
          'token': session.token,
          'expires_at': session.expiresAt.toIso8601String(),
          'session_expires_at': session.sessionExpiresAt.toIso8601String(),
          'refresh_token': session.refreshToken,
          'user': session.user,
          'remember_me': true,
        }),
      );
    } else {
      await clearStoredSession();
    }
    return session;
  }

  Future<void> clearStoredSession() async {
    await _storage.delete(_sessionKey);
    await _storage.delete(_legacySessionKey);
  }

  Future<void> _revokeStoredSession() async {
    final raw = await _storage.read(_sessionKey);
    Object? revocationFailure;
    if (raw != null) {
      try {
        final map = jsonDecode(raw) as Map<String, dynamic>;
        if (map['remember_me'] == true &&
            map['refresh_token'] is String &&
            map['session_expires_at'] is String) {
          final saved = ApiSession(
            token: map['token'] as String,
            expiresAt: DateTime.parse(map['expires_at'] as String),
            sessionExpiresAt: DateTime.parse(
              map['session_expires_at'] as String,
            ),
            refreshToken: map['refresh_token'] as String,
            user: Map<String, dynamic>.from(map['user'] as Map),
            rememberMe: true,
          );
          try {
            await _request(
              'POST',
              '/auth/logout',
              session: saved,
              allowEmpty: true,
            );
          } on ApiException catch (error) {
            // A session the server already rejects needs no further revocation.
            if (error.statusCode != 401 && error.statusCode != 403) {
              revocationFailure = error;
            }
          } catch (error) {
            revocationFailure = error;
          }
        }
      } catch (_) {
        // Malformed or old local state is not used as authentication.
      }
    }
    await clearStoredSession();
    if (revocationFailure != null) {
      throw const ApiException(
        'Could not confirm logout of the previous account. Check your connection and try again.',
      );
    }
  }

  Future<void> _ensureFreshSession(ApiSession session) async {
    if (!session.rememberMe ||
        session.expiresAt.isAfter(
          DateTime.now().toUtc().add(const Duration(minutes: 1)),
        )) {
      return;
    }
    if (session.refreshToken == null ||
        !session.sessionExpiresAt.isAfter(DateTime.now().toUtc())) {
      sessionExpired.value = true;
      await clearStoredSession();
      throw const ApiException(
        'Your remembered session expired. Sign in again.',
        statusCode: 401,
      );
    }
    final pending = _refreshing;
    if (pending != null) {
      await pending;
      return;
    }
    final task = _refreshSession(session);
    _refreshing = task;
    try {
      await task;
    } finally {
      if (identical(_refreshing, task)) _refreshing = null;
    }
  }

  Future<void> _refreshSession(ApiSession session) async {
    try {
      final json = await _request(
        'POST',
        '/auth/refresh',
        body: {'refresh_token': session.refreshToken},
      );
      session.token = json['access_token'] as String;
      session.expiresAt = DateTime.parse(json['expires_at'] as String).toUtc();
      session.refreshToken = json['refresh_token'] as String;
      session.sessionExpiresAt = DateTime.parse(
        json['session_expires_at'] as String,
      ).toUtc();
      await _storage.write(
        _sessionKey,
        jsonEncode({
          'token': session.token,
          'expires_at': session.expiresAt.toIso8601String(),
          'session_expires_at': session.sessionExpiresAt.toIso8601String(),
          'refresh_token': session.refreshToken,
          'user': session.user,
          'remember_me': true,
        }),
      );
    } on ApiException catch (e) {
      if (e.statusCode == 401 || e.statusCode == 403) {
        sessionExpired.value = true;
        await clearStoredSession();
      }
      rethrow;
    } catch (_) {
      throw const ApiException(
        'Could not refresh the remembered session. Retry when online.',
      );
    }
  }

  Future<void> logout(ApiSession session) async {
    try {
      await _request(
        'POST',
        '/auth/logout',
        session: session,
        allowEmpty: true,
      );
    } finally {
      await clearStoredSession();
    }
  }

  Future<Map<String, dynamic>> get(String path, ApiSession session) =>
      _request('GET', path, session: session);

  Future<List<dynamic>> getList(String path, ApiSession session) async =>
      await _requestList(path, session);

  Future<List<dynamic>> _requestList(String path, ApiSession session) async {
    final response = await _send('GET', path, session: session);
    final value = jsonDecode(response.body);
    if (value is List) return value;
    if (value is Map && value['items'] is List) {
      return value['items'] as List<dynamic>;
    }
    throw const ApiException(
      'The server returned an unexpected list response.',
    );
  }

  Future<Map<String, dynamic>> post(
    String path,
    ApiSession session, {
    Map<String, dynamic>? body,
    String? idempotencyKey,
  }) => _request(
    'POST',
    path,
    session: session,
    body: body,
    idempotencyKey: idempotencyKey,
  );

  Future<Map<String, dynamic>> patch(
    String path,
    ApiSession session, {
    Map<String, dynamic>? body,
  }) => _request('PATCH', path, session: session, body: body);

  Future<Map<String, dynamic>> put(
    String path,
    ApiSession session, {
    Map<String, dynamic>? body,
  }) => _request('PUT', path, session: session, body: body);

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    ApiSession? session,
    Map<String, dynamic>? body,
    String? idempotencyKey,
    bool allowEmpty = false,
  }) async {
    final response = await _send(
      method,
      path,
      session: session,
      body: body,
      idempotencyKey: idempotencyKey,
    );
    if (allowEmpty && response.statusCode == 204) return {};
    final decoded = jsonDecode(response.body);
    return Map<String, dynamic>.from(decoded as Map);
  }

  Future<http.Response> _send(
    String method,
    String path, {
    ApiSession? session,
    Map<String, dynamic>? body,
    String? idempotencyKey,
  }) async {
    if (!configured) {
      throw const ApiException(
        'The shared service URL is not configured. Build with --dart-define=API_BASE_URL=https://your-api-host.',
      );
    }
    if (session != null && path != '/auth/refresh' && path != '/auth/me') {
      await _ensureFreshSession(session);
    }
    final uri = Uri.parse('$baseUrl/api/v1$path');
    final headers = <String, String>{'Accept': 'application/json'};
    if (body != null) headers['Content-Type'] = 'application/json';
    if (session != null) headers['Authorization'] = 'Bearer ${session.token}';
    if (idempotencyKey != null) headers['Idempotency-Key'] = idempotencyKey;
    try {
      final request = http.Request(method, uri)..headers.addAll(headers);
      if (body != null) request.body = jsonEncode(body);
      final streamed = await _http
          .send(request)
          .timeout(const Duration(seconds: 15));
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode >= 200 && response.statusCode < 300) {
        return response;
      }
      var message = response.statusCode >= 500
          ? 'The coordination service had a problem. Please retry; if it continues, ask the server operator to check the service.'
          : 'Service request failed (${response.statusCode}).';
      if (response.statusCode == 401 &&
          session != null &&
          path != '/auth/logout' &&
          path != '/auth/me') {
        sessionExpired.value = true;
      }
      if (response.statusCode < 500) {
        try {
          final data = jsonDecode(response.body) as Map;
          final detail = data['detail'];
          message = detail is String ? detail : message;
        } catch (_) {}
      }
      throw ApiException(message, statusCode: response.statusCode);
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(
        'Could not reach the coordination service. Check your connection and retry.',
      );
    }
  }

  static String newIdempotencyKey() {
    final bytes = List<int>.generate(24, (_) => Random.secure().nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }
}
