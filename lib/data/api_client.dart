import 'dart:convert';
import 'dart:math';

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
  const ApiSession({
    required this.token,
    required this.expiresAt,
    required this.user,
  });
  final String token;
  final DateTime expiresAt;
  final Map<String, dynamic> user;
  String get role => user['role'] as String;
}

class ApiClient {
  ApiClient({
    String? baseUrl,
    http.Client? client,
    FlutterSecureStorage? storage,
  }) : baseUrl = (baseUrl ?? const String.fromEnvironment('API_BASE_URL'))
           .replaceAll(RegExp(r'/$'), ''),
       _http = client ?? http.Client(),
       _storage = storage ?? const FlutterSecureStorage();

  final String baseUrl;
  final http.Client _http;
  final FlutterSecureStorage _storage;
  static const _sessionKey = 'coordination_api_session_v1';

  bool get configured =>
      baseUrl.startsWith('https://') || baseUrl.startsWith('http://');

  Future<ApiSession?> restoreSession() async {
    final raw = await _storage.read(key: _sessionKey);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      final session = ApiSession(
        token: map['token'] as String,
        expiresAt: DateTime.parse(map['expires_at'] as String),
        user: Map<String, dynamic>.from(map['user'] as Map),
      );
      if (!session.expiresAt.isAfter(DateTime.now().toUtc())) {
        await _storage.delete(key: _sessionKey);
        return null;
      }
      return session;
    } catch (_) {
      await _storage.delete(key: _sessionKey);
      return null;
    }
  }

  Future<ApiSession> login(String email, String password, String portal) async {
    final json = await _request(
      'POST',
      '/auth/login',
      body: {'email': email.trim(), 'password': password, 'portal': portal},
    );
    return _saveSession(json);
  }

  Future<ApiSession> registerUser(
    String name,
    String email,
    String password,
  ) async {
    final json = await _request(
      'POST',
      '/auth/register',
      body: {
        'display_name': name.trim(),
        'email': email.trim(),
        'password': password,
      },
    );
    return _saveSession(json);
  }

  Future<ApiSession> _saveSession(Map<String, dynamic> json) async {
    final session = ApiSession(
      token: json['access_token'] as String,
      expiresAt: DateTime.parse(json['expires_at'] as String).toUtc(),
      user: Map<String, dynamic>.from(json['user'] as Map),
    );
    await _storage.write(
      key: _sessionKey,
      value: jsonEncode({
        'token': session.token,
        'expires_at': session.expiresAt.toIso8601String(),
        'user': session.user,
      }),
    );
    return session;
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
      await _storage.delete(key: _sessionKey);
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
      var message = 'Service request failed (${response.statusCode}).';
      try {
        final data = jsonDecode(response.body) as Map;
        final detail = data['detail'];
        message = detail is String ? detail : message;
      } catch (_) {}
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
