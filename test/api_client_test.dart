import 'dart:convert';
import 'dart:io';

import 'package:emergency_coordination_system/data/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

const sessionKey = 'coordination_api_session_v2';
const legacySessionKey = 'coordination_api_session_v1';

class MemorySessionStorage implements ApiSessionStorage {
  final values = <String, String>{};

  @override
  Future<void> delete(String key) async {
    values.remove(key);
  }

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }
}

Map<String, dynamic> authResponse({String role = 'admin'}) => {
  'access_token': 'test-access-token',
  'expires_at': DateTime.now()
      .toUtc()
      .add(const Duration(minutes: 30))
      .toIso8601String(),
  'refresh_token': 'test-refresh-token-012345678901234567890123456789',
  'session_expires_at': DateTime.now()
      .toUtc()
      .add(const Duration(days: 30))
      .toIso8601String(),
  'user': {'id': 'user-1', 'email': 'admin@example.com', 'role': role},
};

void main() {
  group('remembered sessions', () {
    test(
      'Remember Me stores only the server-issued session in secure storage',
      () async {
        final storage = MemorySessionStorage();
        final client = ApiClient(
          baseUrl: 'https://api.example.test',
          storage: storage,
          client: MockClient((request) async {
            expect(jsonDecode(request.body)['remember_me'], isTrue);
            return http.Response(jsonEncode(authResponse()), 200);
          }),
        );

        final session = await client.login(
          'admin@example.com',
          'password',
          'admin',
          rememberMe: true,
        );

        expect(session.rememberMe, isTrue);
        expect(storage.values[sessionKey], contains('test-access-token'));
        expect(storage.values[sessionKey], contains('"remember_me":true'));
        expect(storage.values[sessionKey], contains('test-refresh-token'));
        expect(storage.values, isNot(contains(legacySessionKey)));
      },
    );

    test('unchecked Remember Me does not persist a session', () async {
      final storage = MemorySessionStorage()
        ..values[sessionKey] = 'previous account session'
        ..values[legacySessionKey] = 'legacy session';
      final client = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: storage,
        client: MockClient(
          (_) async => http.Response(jsonEncode(authResponse()), 200),
        ),
      );

      final session = await client.login(
        'admin@example.com',
        'password',
        'admin',
        rememberMe: false,
      );

      expect(session.rememberMe, isFalse);
      expect(storage.values, isEmpty);
    });

    test(
      'switching accounts revokes the previous remembered session first',
      () async {
        final storage = _storedSession();
        final requests = <String>[];
        final client = ApiClient(
          baseUrl: 'https://api.example.test',
          storage: storage,
          client: MockClient((request) async {
            requests.add(request.url.path);
            if (request.url.path == '/api/v1/auth/logout') {
              return http.Response('', 204);
            }
            return http.Response(jsonEncode(authResponse(role: 'user')), 200);
          }),
        );

        await client.login(
          'caller@example.com',
          'password',
          'user',
          rememberMe: false,
        );

        expect(requests, ['/api/v1/auth/logout', '/api/v1/auth/login']);
        expect(storage.values, isEmpty);
      },
    );

    test(
      'does not log in as another account when revocation is unconfirmed',
      () async {
        final storage = _storedSession();
        final requests = <String>[];
        final client = ApiClient(
          baseUrl: 'https://api.example.test',
          storage: storage,
          client: MockClient((request) async {
            requests.add(request.url.path);
            return http.Response('{"detail":"Service unavailable"}', 503);
          }),
        );

        await expectLater(
          client.login(
            'new@example.com',
            'password',
            'user',
            rememberMe: false,
          ),
          throwsA(isA<ApiException>()),
        );

        expect(requests, ['/api/v1/auth/logout']);
        expect(storage.values, isEmpty);
      },
    );

    test('restoration validates the token and role with the backend', () async {
      final storage = _storedSession();
      final client = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: storage,
        client: MockClient((request) async {
          expect(request.url.path, '/api/v1/auth/me');
          expect(request.headers['authorization'], 'Bearer test-access-token');
          return http.Response(
            jsonEncode({
              'id': 'user-1',
              'email': 'admin@example.com',
              'role': 'admin',
            }),
            200,
          );
        }),
      );

      final restored = await client.restoreSession();

      expect(restored?.role, 'admin');
      expect(restored?.rememberMe, isTrue);
    });

    test('access expiry refreshes and rotates the stored credential', () async {
      final storage = _storedSession(expiresSoon: true);
      final client = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: storage,
        client: MockClient((request) async {
          if (request.url.path == '/api/v1/auth/refresh') {
            expect(
              jsonDecode(request.body)['refresh_token'],
              'test-refresh-token-012345678901234567890123456789',
            );
            final response = authResponse();
            response['access_token'] = 'rotated-access-token';
            response['refresh_token'] =
                'rotated-refresh-token-012345678901234567890123456789';
            return http.Response(jsonEncode(response), 200);
          }
          return http.Response(
            jsonEncode({
              'id': 'user-1',
              'email': 'admin@example.com',
              'role': 'admin',
            }),
            200,
          );
        }),
      );

      final restored = await client.restoreSession();

      expect(restored, isNotNull);
      expect(restored!.expiresAt.isAfter(DateTime.now().toUtc()), isTrue);
      expect(storage.values[sessionKey], contains('rotated-access-token'));
      expect(storage.values[sessionKey], contains('rotated-refresh-token'));
    });

    test('expired and revoked sessions are cleared', () async {
      final expiredStorage = _storedSession(expired: true);
      final expiredClient = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: expiredStorage,
        client: MockClient((_) async => http.Response('', 500)),
      );
      expect(await expiredClient.restoreSession(), isNull);
      expect(expiredStorage.values, isEmpty);

      final revokedStorage = _storedSession();
      final revokedClient = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: revokedStorage,
        client: MockClient(
          (_) async => http.Response('{"detail":"Unauthorized"}', 401),
        ),
      );
      expect(await revokedClient.restoreSession(), isNull);
      expect(revokedStorage.values, isEmpty);
    });

    test('backend outage never restores locally cached identity and keeps token for retry', () async {
      final storage = _storedSession();
      final client = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: storage,
        client: MockClient((_) async => throw const SocketException('offline')),
      );

      await expectLater(client.restoreSession(), throwsA(isA<ApiException>()));
      expect(storage.values, contains(sessionKey));
    });

    test('role mismatch clears a remembered session', () async {
      final storage = _storedSession();
      final client = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: storage,
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'id': 'user-1',
              'email': 'admin@example.com',
              'role': 'responder',
            }),
            200,
          ),
        ),
      );

      expect(await client.restoreSession(), isNull);
      expect(storage.values, isEmpty);
    });

    test(
      'logout clears credentials even when server revocation fails',
      () async {
        final storage = _storedSession();
        final session = ApiSession(
          token: 'test-access-token',
          expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 30)),
          sessionExpiresAt: DateTime.now().toUtc().add(const Duration(days: 1)),
          refreshToken: 'test-refresh-token-012345678901234567890123456789',
          user: {'id': 'user-1', 'email': 'admin@example.com', 'role': 'admin'},
          rememberMe: true,
        );
        final client = ApiClient(
          baseUrl: 'https://api.example.test',
          storage: storage,
          client: MockClient(
            (_) async => http.Response('{"detail":"unavailable"}', 503),
          ),
        );

        await expectLater(client.logout(session), throwsA(isA<ApiException>()));
        expect(storage.values, isEmpty);
      },
    );
  });
}

MemorySessionStorage _storedSession({
  bool expired = false,
  bool expiresSoon = false,
}) {
  final storage = MemorySessionStorage();
  final expires = DateTime.now().toUtc().add(
    expired ? const Duration(seconds: -1) : const Duration(days: 30),
  );
  storage.values[sessionKey] = jsonEncode({
    'token': 'test-access-token',
    'expires_at':
        (expired
                ? expires
                : DateTime.now().toUtc().add(
                    expiresSoon
                        ? const Duration(seconds: 20)
                        : const Duration(minutes: 20),
                  ))
            .toIso8601String(),
    'session_expires_at': expires.toIso8601String(),
    'refresh_token': 'test-refresh-token-012345678901234567890123456789',
    'user': {'id': 'user-1', 'email': 'admin@example.com', 'role': 'admin'},
    'remember_me': true,
  });
  return storage;
}
