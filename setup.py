from setuptools import setup

setup(name='drupal-scout',
      version='0.2.0',
      description='Scout out for transitive versions of Drupal modules for the upgrade of the core.',
      url='https://github.com/rtech91/drupal-scout',
      keywords='drupal scout upgrade update',
      author='Andrew [R-Tech] Tsyganiuk',
      author_email='in0mad91@gmail.com',
      packages=['drupal_scout'],
      scripts=['bin/drupal-scout'],
      install_requires=[
            'jq',
            'argparse',
            'requests'
      ],
      test_suite='nose.collector',
      tests_require=['nose', 'coverage'],
      zip_safe=False)
