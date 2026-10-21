import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:emergency_coordination_system/domain/models.dart';
import 'package:emergency_coordination_system/presentation/home_page.dart';

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

}
