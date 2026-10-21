import 'package:flutter_test/flutter_test.dart';
import 'package:emergency_coordination_system/domain/dispatch_rules.dart';
import 'package:emergency_coordination_system/domain/models.dart';

void main() {
  group('dispatch decision support', () {
    test('higher severity and urgency produce critical priority', () {
      final d = assessPriority(type: 'Medical', severity: 5, urgency: 5);
      expect(d.priority, Priority.critical);
      expect(d.reason, contains('Severity 5/5'));
    });
    test('low urgency and severity remain low priority', () {
      expect(
        assessPriority(type: 'Utility', severity: 1, urgency: 1).priority,
        Priority.low,
      );
    });
    test('distance is zero for the same point and symmetric', () {
      expect(distanceKm(30.7, 76.7, 30.7, 76.7), 0);
      expect(
        distanceKm(30.7, 76.7, 30.8, 76.8),
        closeTo(distanceKm(30.8, 76.8, 30.7, 76.7), 1e-8),
      );
    });
    test('only forward response states are legal', () {
      expect(
        canTransition(IncidentStatus.assigned, IncidentStatus.enRoute),
        isTrue,
      );
      expect(
        canTransition(IncidentStatus.assigned, IncidentStatus.resolved),
        isFalse,
      );
      expect(
        canTransition(IncidentStatus.responding, IncidentStatus.resolved),
        isTrue,
      );
    });
  });
}
