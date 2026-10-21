import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:emergency_coordination_system/data/api_client.dart';
import 'package:emergency_coordination_system/domain/models.dart';
import 'package:emergency_coordination_system/presentation/home_page.dart';
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
    await tester.tap(find.text('Sign in'));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.textContaining('API_BASE_URL'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
