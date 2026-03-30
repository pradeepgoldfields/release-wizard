pipeline {
    agent {
        // Use a UBI-based agent so the build environment mirrors production
        kubernetes {
            yaml """
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: python
    image: registry.access.redhat.com/ubi9/python-312
    command: ['cat']
    tty: true
  - name: podman
    image: quay.io/podman/stable:latest
    command: ['cat']
    tty: true
    securityContext:
      privileged: true
"""
        }
    }

    environment {
        APP_NAME     = 'release-wizard'
        IMAGE_REPO   = "your-registry.example.com/${APP_NAME}"
        IMAGE_TAG    = "${env.GIT_COMMIT?.take(8) ?: 'latest'}"
        FULL_IMAGE   = "${IMAGE_REPO}:${IMAGE_TAG}"
        REGISTRY_CREDENTIALS = credentials('registry-credentials-id')
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {

        stage('Install Dependencies') {
            steps {
                container('python') {
                    sh '''
                        python -m pip install --upgrade pip
                        pip install -r requirements-dev.txt
                    '''
                }
            }
        }

        stage('Lint') {
            steps {
                container('python') {
                    sh 'ruff check .'
                    sh 'ruff format --check .'
                }
            }
        }

        stage('Unit Tests') {
            steps {
                container('python') {
                    sh 'pytest tests/unit --cov=app --cov-report=xml --cov-report=term-missing -v'
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: '**/pytest-report.xml'
                    publishCoverage adapters: [coberturaAdapter('coverage.xml')], sourceFileResolver: sourceFiles('STORE_LAST_BUILD')
                }
            }
        }

        stage('Integration Tests') {
            steps {
                container('python') {
                    sh 'pytest tests/integration -v'
                }
            }
        }

        stage('Build Image') {
            steps {
                container('podman') {
                    sh "podman build -t ${FULL_IMAGE} ."
                }
            }
        }

        stage('Push Image') {
            when {
                anyOf {
                    branch 'main'
                    branch 'release/*'
                }
            }
            steps {
                container('podman') {
                    sh """
                        echo "${REGISTRY_CREDENTIALS_PSW}" | podman login ${IMAGE_REPO} \
                            -u "${REGISTRY_CREDENTIALS_USR}" --password-stdin
                        podman push ${FULL_IMAGE}
                    """
                }
            }
        }

        stage('Deploy to Dev') {
            when { branch 'main' }
            steps {
                // Replace image tag in the deployment manifest and apply
                sh """
                    sed -i 's|image: .*|image: ${FULL_IMAGE}|g' k8s/deployment.yaml
                    kubectl apply -f k8s/ --namespace=release-wizard-dev
                    kubectl rollout status deployment/${APP_NAME} --namespace=release-wizard-dev --timeout=120s
                """
            }
        }

        stage('Deploy to Prod') {
            when { branch 'release/*' }
            input {
                message 'Deploy to production?'
                ok 'Deploy'
            }
            steps {
                sh """
                    sed -i 's|image: .*|image: ${FULL_IMAGE}|g' k8s/deployment.yaml
                    kubectl apply -f k8s/ --namespace=release-wizard-prod
                    kubectl rollout status deployment/${APP_NAME} --namespace=release-wizard-prod --timeout=180s
                """
            }
        }
    }

    post {
        failure {
            echo "Pipeline failed — check logs above."
            // Add Slack / email notification here
        }
        cleanup {
            container('podman') {
                sh "podman rmi ${FULL_IMAGE} || true"
            }
        }
    }
}
