import 'package:flutter_test/flutter_test.dart';

import 'dart:io';

import 'package:emergency_coordination_system/data/operations_store.dart';
import 'package:emergency_coordination_system/domain/models.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'assignment, lifecycle, message and persistence work together',
    () async {
      final directory = await Directory.systemTemp.createTemp('ecs-store-');
      addTearDown(() => directory.delete(recursive: true));
      final store = OperationsStore(File('${directory.path}/workspace.json'));
      await store.load();
      final incident = await store.createIncident(
        type: 'Medical',
        description: 'Practice scenario',
        location: 'Sector 68',
        lat: 30.7047,
        lon: 76.7185,
        severity: 4,
        urgency: 4,
      );
      final match = store.recommendations(incident).first;
      final concurrent = await store.createIncident(
        type: 'Medical',
        description: 'Second practice scenario',
        location: 'Phase 6',
        lat: 30.704,
        lon: 76.729,
        severity: 3,
        urgency: 3,
      );
      await store.assign(incident, match);
      expect(
        store.recommendations(concurrent).map((r) => r.id),
        isNot(contains(match.id)),
      );
      expect(incident.status, IncidentStatus.assigned);
      expect(match.status, ResponderStatus.assigned);
      expect(
        store.resources.where((r) => r.incidentId == incident.id),
        hasLength(1),
      );
      await store.sendMessage(
        incident,
        sender: 'Desk',
        role: 'Coordinator',
        body: 'Proceed',
      );
      expect(store.thread(incident.id).single.body, 'Proceed');
      await store.advance(incident);
      await store.advance(incident);
      await store.advance(incident);
      expect(incident.status, IncidentStatus.resolved);
      expect(match.status, ResponderStatus.available);
      expect(
        store.resources.where((r) => r.incidentId == incident.id),
        isEmpty,
      );
      final restored = OperationsStore(
        File('${directory.path}/workspace.json'),
      );
      await restored.load();
      expect(
        restored.incidents.singleWhere((i) => i.id == incident.id).status,
        IncidentStatus.resolved,
      );
      expect(restored.thread(incident.id).single.body, 'Proceed');
    },
  );

  test('off duty responders are excluded from recommendations', () async {
    final directory = await Directory.systemTemp.createTemp('ecs-store-');
    addTearDown(() => directory.delete(recursive: true));
    final store = OperationsStore(File('${directory.path}/workspace.json'));
    await store.load();
    final incident = await store.createIncident(
      type: 'Fire',
      description: 'Practice fire scenario',
      location: 'Phase 6',
      lat: 30.704,
      lon: 76.729,
      severity: 3,
      urgency: 4,
    );
    final fireTeam = store.responders.singleWhere((r) => r.id == 'r2');
    await store.setAvailability(fireTeam, false);
    expect(
      store.recommendations(incident).map((r) => r.id),
      isNot(contains('r2')),
    );
    await store.setAvailability(fireTeam, true);
    expect(store.recommendations(incident).map((r) => r.id), contains('r2'));
  });
}
