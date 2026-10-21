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
