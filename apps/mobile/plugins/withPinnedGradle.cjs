const { withDangerousMod } = require('@expo/config-plugins');
const fs = require('node:fs');
const path = require('node:path');

// SDK 56 template currently selects Gradle 9, but RN 0.85's Foojay plugin
// references IBM_SEMERU removed in Gradle 9. Keep AGP 8.12 on Gradle 8.14.3.
module.exports = function withPinnedGradle(config) {
  return withDangerousMod(config, ['android', async (mod) => {
    const file = path.join(mod.modRequest.platformProjectRoot, 'gradle/wrapper/gradle-wrapper.properties');
    let source = fs.readFileSync(file, 'utf8');
    source = source.replace(/^distributionUrl=.*$/m,
      'distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14.3-bin.zip');
    source = source.replace(/^distributionSha256Sum=.*\n?/m, '');
    source += '\ndistributionSha256Sum=bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531\n';
    fs.writeFileSync(file, source);
    return mod;
  }]);
};
