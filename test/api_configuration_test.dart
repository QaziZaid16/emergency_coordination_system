import 'package:emergency_coordination_system/data/api_configuration.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('release requires a real HTTPS API origin', () {
    expect(
      ApiConfiguration(
        'https://api.coordination-platform.net',
        releaseMode: true,
      ).isValid,
      isTrue,
    );
    expect(
      ApiConfiguration('https://your-api-host', releaseMode: true).isValid,
      isFalse,
    );
    expect(
      ApiConfiguration('http://api.example.net', releaseMode: true).isValid,
      isFalse,
    );
    expect(
      ApiConfiguration('https://api.example.test', releaseMode: true).isValid,
      isFalse,
    );
    expect(
      ApiConfiguration('https://api.example.com', releaseMode: true).isValid,
      isFalse,
    );
  });

  test('development HTTP is limited to local development hosts', () {
    expect(
      ApiConfiguration('http://127.0.0.1:8000', releaseMode: false).isValid,
      isTrue,
    );
    expect(
      ApiConfiguration('http://10.0.2.2:8000', releaseMode: false).isValid,
      isTrue,
    );
    expect(
      ApiConfiguration(
        'http://coordination.example.net',
        releaseMode: false,
      ).isValid,
      isFalse,
    );
    expect(ApiConfiguration('', releaseMode: false).isValid, isFalse);
    expect(ApiConfiguration('not a url', releaseMode: false).isValid, isFalse);
  });
}
