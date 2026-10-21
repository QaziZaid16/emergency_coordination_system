import 'dart:math' as math;

import 'models.dart';

class PriorityDecision {
  const PriorityDecision(this.priority, this.score, this.reason);
  final Priority priority;
  final int score;
  final String reason;
}

PriorityDecision assessPriority({
  required String type,
  required int severity,
  required int urgency,
}) {
  final category = switch (type) {
    'Medical' => 2,
    'Fire' => 2,
    'Rescue' => 1,
    'Security' => 1,
    _ => 0,
  };
  final score =
      (severity.clamp(1, 5) * 2) + (urgency.clamp(1, 5) * 2) + category;
  final priority = score >= 18
      ? Priority.critical
      : score >= 14
      ? Priority.high
      : score >= 9
      ? Priority.medium
      : Priority.low;
  final reason =
      'Severity $severity/5 + urgency $urgency/5${category > 0 ? ' + $type response factor' : ''} = $score/22';
  return PriorityDecision(priority, score, reason);
}

double distanceKm(double lat1, double lon1, double lat2, double lon2) {
  const r = 6371.0;
  final dLat = _rad(lat2 - lat1), dLon = _rad(lon2 - lon1);
  final a =
      math.pow(math.sin(dLat / 2), 2) +
      math.cos(_rad(lat1)) *
          math.cos(_rad(lat2)) *
          math.pow(math.sin(dLon / 2), 2);
  return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
}

double _rad(double deg) => deg * math.pi / 180;

bool canTransition(IncidentStatus from, IncidentStatus to) =>
    switch ((from, to)) {
      (IncidentStatus.queued, IncidentStatus.assigned) => true,
      (IncidentStatus.assigned, IncidentStatus.enRoute) => true,
      (IncidentStatus.enRoute, IncidentStatus.responding) => true,
      (IncidentStatus.responding, IncidentStatus.resolved) => true,
      _ => false,
    };
