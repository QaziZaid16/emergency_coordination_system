import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;
import 'package:emergency_coordination_system/data/api_client.dart';
import 'package:emergency_coordination_system/data/operations_store.dart';
import 'package:emergency_coordination_system/domain/models.dart';
import 'package:emergency_coordination_system/presentation/home_page.dart';
import 'package:emergency_coordination_system/presentation/design_system.dart';
import 'package:emergency_coordination_system/presentation/portals.dart';

void main() {
  testWidgets('priority badge renders a clear critical label', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(child: PriorityPill(priority: Priority.critical)),
        ),
      ),
    );
    expect(find.text('CRITICAL'), findsOneWidget);
  });

  testWidgets('admin sign-in explains backend configuration', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: OpsTheme.dark,
        home: PortalLoginPage(
          api: ApiClient(baseUrl: ''),
          role: 'admin',
          onSignedIn: (_) {},
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Admin Portal'), findsWidgets);
    expect(find.text('Service URL not configured'), findsOneWidget);
    final rememberTile = tester.widget<CheckboxListTile>(
      find.byType(CheckboxListTile),
    );
    expect(rememberTile.value, isFalse);
    await tester.tap(find.text('Remember me on this device'));
    await tester.pump();
    expect(
      tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,
      isTrue,
    );
    await tester.tap(find.text('Sign in'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.textContaining('API_BASE_URL'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'admin incident cards show readable summaries and full details on demand',
    (tester) async {
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final incident = {
        'id': 'incident-1',
        'reference': 'ECS-B61659',
        'emergency_type': 'Ambulance / Medical Emergency',
        'status': 'Unassigned',
        'priority': 'High',
        'severity': 3,
        'urgency': 3,
        'created_at': '2026-10-21T18:12:44.153400Z',
        'priority_reason':
            'Severity 3/5 + urgency 3/5 + response factor = 14/22',
        'description': 'Bridge collapse',
        'location_label': 'Device GPS (30.72691, 76.65173)',
        'latitude': 30.7269108,
        'longitude': 76.6517281,
        'accuracy_m': 13,
        'analysis': {
          'status': 'ready',
          'provider': 'rules_baseline',
          'result': {
            'summary': 'Bridge collapse',
            'hazards_to_verify': [
              {'statement': 'collapse'},
            ],
            'explanation': 'Source-matched text only.',
          },
        },
      };
      final api = ApiClient(
        baseUrl: 'https://api.example.test',
        client: MockClient((request) async {
          if (request.url.path.endsWith('/duplicates')) {
            return http.Response(
              jsonEncode({'candidates': [], 'auto_merge': false}),
              200,
            );
          }
          if (request.url.path.endsWith('/incidents')) {
            return http.Response(jsonEncode([incident]), 200);
          }
          if (request.url.path.endsWith('/dashboard')) {
            return http.Response('{}', 200);
          }
          return http.Response('[]', 200);
        }),
      );
      final session = ApiSession(
        token: 'admin-token',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
        sessionExpiresAt: DateTime.now().add(const Duration(days: 1)),
        user: {'id': 'admin-1', 'email': 'admin@example.test', 'role': 'admin'},
        rememberMe: false,
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: OpsTheme.dark,
          home: AdminPortal(api: api, session: session, onLogout: () {}),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Incidents'));
      await tester.pumpAndSettle();

      expect(find.text('Assign responder'), findsOneWidget);
      expect(find.text('Severity 3/5'), findsOneWidget);
      expect(find.text('Urgency 3/5'), findsOneWidget);
      expect(
        find.byWidgetPredicate(
          (widget) =>
              widget is Text &&
              RegExp(r'21 Oct \d{2}:\d{2}').hasMatch(widget.data ?? ''),
        ),
        findsOneWidget,
      );
      expect(
        find.text('GPS location shared · tap for coordinates'),
        findsOneWidget,
      );
      expect(find.textContaining('30.7269108'), findsNothing);
      expect(find.textContaining('response factor'), findsNothing);
      expect(find.text('More'), findsOneWidget);
      await tester.tap(find.text('More'));
      await tester.pumpAndSettle();
      expect(find.text('Mark resolved'), findsOneWidget);
      expect(find.text('Cancel report'), findsOneWidget);
      await tester.tapAt(const Offset(10, 100));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Ambulance / Medical Emergency'));
      await tester.pumpAndSettle();
      expect(find.text('Priority explanation'), findsOneWidget);
      expect(find.text('GPS coordinates'), findsOneWidget);
      expect(find.textContaining('30.7269108'), findsOneWidget);
      expect(find.textContaining('Rules-based text scan'), findsOneWidget);
      expect(find.text('No similar reports found for review.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('admin copilot returns a cited read-only operational answer', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1200, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = ApiClient(
      baseUrl: 'https://api.example.test',
      client: MockClient((request) async {
        if (request.url.path.endsWith('/dashboard')) {
          return http.Response('{}', 200);
        }
        if (request.url.path.endsWith('/incidents')) {
          return http.Response('[]', 200);
        }
        if (request.url.path.endsWith('/copilot')) {
          return http.Response(
            jsonEncode({
              'answer': '1 report awaits assignment: ECS-CASE01.',
              'intent': 'unassigned_incidents',
              'sources': [
                {
                  'reference': 'ECS-CASE01',
                  'emergency_type': 'Fire and Rescue',
                },
              ],
              'read_only': true,
              'generated_by': 'rules_based',
            }),
            200,
          );
        }
        return http.Response('[]', 200);
      }),
    );
    final session = ApiSession(
      token: 'admin-token',
      expiresAt: DateTime.now().add(const Duration(hours: 1)),
      sessionExpiresAt: DateTime.now().add(const Duration(days: 1)),
      user: {'id': 'admin-1', 'email': 'admin@example.test', 'role': 'admin'},
      rememberMe: false,
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: OpsTheme.dark,
        home: AdminPortal(api: api, session: session, onLogout: () {}),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Copilot'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Unassigned reports'));
    await tester.pumpAndSettle();
    expect(find.textContaining('ECS-CASE01'), findsNWidgets(2));
    expect(
      find.textContaining('Database answer · rules-based'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'remembered user restores only to the user portal and logout returns to chooser',
    (tester) async {
      final storage = _TestSessionStorage();
      storage.values['coordination_api_session_v2'] = jsonEncode({
        'token': 'remembered-user-token',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(minutes: 20))
            .toIso8601String(),
        'session_expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(days: 2))
            .toIso8601String(),
        'refresh_token':
            'remembered-refresh-token-012345678901234567890123456789',
        'user': {'id': 'user-1', 'email': 'caller@example.com', 'role': 'user'},
        'remember_me': true,
      });
      final api = ApiClient(
        baseUrl: 'https://api.example.test',
        storage: storage,
        client: MockClient((request) async {
          if (request.url.path == '/api/v1/auth/me') {
            return http.Response(
              jsonEncode({
                'id': 'user-1',
                'email': 'caller@example.com',
                'role': 'user',
              }),
              200,
            );
          }
          if (request.url.path == '/api/v1/incidents') {
            return http.Response('[]', 200);
          }
          if (request.url.path == '/api/v1/auth/logout') {
            return http.Response('', 204);
          }
          return http.Response('{}', 200);
        }),
      );
      final store = OperationsStore(File('/tmp/remembered-portal-widget.json'));

      await tester.pumpWidget(
        MaterialApp(
          theme: OpsTheme.dark,
          home: PortalEntryPage(api: api, trainingStore: store),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('User Portal'), findsOneWidget);
      expect(find.text('SOS · Request help'), findsOneWidget);
      expect(find.text('Admin Portal'), findsNothing);

      await tester.tap(find.byTooltip('Sign out'));
      await tester.pumpAndSettle();
      expect(find.text('Choose your portal'), findsOneWidget);
      expect(storage.values, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('revoked active session returns to the portal chooser', (
    tester,
  ) async {
    final storage = _TestSessionStorage();
    storage.values['coordination_api_session_v2'] = jsonEncode({
      'token': 'revoked-user-token',
      'expires_at': DateTime.now()
          .toUtc()
          .add(const Duration(minutes: 20))
          .toIso8601String(),
      'session_expires_at': DateTime.now()
          .toUtc()
          .add(const Duration(days: 2))
          .toIso8601String(),
      'refresh_token': 'revoked-refresh-token-012345678901234567890123456789',
      'user': {'id': 'user-1', 'email': 'caller@example.com', 'role': 'user'},
      'remember_me': true,
    });
    final api = ApiClient(
      baseUrl: 'https://api.example.test',
      storage: storage,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/auth/me') {
          return http.Response(
            jsonEncode({
              'id': 'user-1',
              'email': 'caller@example.com',
              'role': 'user',
            }),
            200,
          );
        }
        return http.Response('{"detail":"Session revoked"}', 401);
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: OpsTheme.dark,
        home: PortalEntryPage(
          api: api,
          trainingStore: OperationsStore(
            File('/tmp/revoked-portal-widget.json'),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Choose your portal'), findsOneWidget);
    expect(
      find.text('Your session expired or was revoked. Sign in again.'),
      findsOneWidget,
    );
    expect(storage.values, isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets('sign-in stays usable on a narrow screen with larger text', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 560);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        theme: OpsTheme.dark,
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.35)),
          child: PortalLoginPage(
            api: ApiClient(baseUrl: ''),
            role: 'responder',
            onSignedIn: (_) {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Sign in to Responder Portal'), findsOneWidget);
    expect(find.text('Remember me on this device'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('official SVG brand mark renders with the dark design system', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: OpsTheme.dark,
        home: const Scaffold(
          body: Center(child: CoordinationBrandMark(size: 72)),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(SvgPicture), findsOneWidget);
    expect(
      find.bySemanticsLabel('Emergency Coordination System logo'),
      findsOneWidget,
    );
    expect(OpsTheme.dark.brightness, Brightness.dark);
    expect(tester.takeException(), isNull);
  });

  testWidgets('dark training workspace remains usable on a compact display', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final store = OperationsStore(File('/tmp/dark-training-widget.json'));
    await tester.runAsync(store.load);

    await tester.pumpWidget(
      MaterialApp(
        theme: OpsTheme.dark,
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.25)),
          child: HomePage(store: store),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 250));
    final titles = [
      'Operations overview',
      'Incident queue',
      'Response teams',
      'Resource board',
      'Activity & reports',
    ];
    for (var destination = 0; destination < titles.length; destination++) {
      final navigation = tester.widget<NavigationBar>(
        find.byType(NavigationBar),
      );
      navigation.onDestinationSelected!(destination);
      await tester.pump(const Duration(milliseconds: 120));
      expect(find.text(titles[destination]), findsOneWidget);
      expect(tester.takeException(), isNull, reason: titles[destination]);
    }

    await tester.pumpWidget(
      MaterialApp(
        theme: OpsTheme.dark,
        home: IncidentDetailPage(
          store: store,
          incident: store.activeIncidents.first,
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 250));
    expect(find.text('CASE LIFECYCLE'), findsOneWidget);
    expect(find.text('Responder recommendation'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

class _TestSessionStorage implements ApiSessionStorage {
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
