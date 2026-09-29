pipeline {
    agent any

    environment {
        DOCKER_REGISTRY = 'docker.io'
        DOCKERHUB_USER = 'pearldias'

        BACKEND_IMAGE = "${DOCKERHUB_USER}/agentic-rag-backend"
        FRONTEND_IMAGE = "${DOCKERHUB_USER}/agentic-rag-frontend"

        K8S_NAMESPACE = 'agentic-rag'
        KUBECONFIG = '/var/jenkins_home/jenkins-kubeconfig.yaml'
        KUBECTL = '/var/jenkins_home/kubectl'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Test Backend') {
            steps {
                sh '''
                    set -e

                    echo "Building backend test image..."
                    docker build \
                        -f backend/Dockerfile \
                        -t agentic-rag-backend-test:${BUILD_NUMBER} \
                        .

                    echo "Running backend tests..."
                    docker run --rm \
                        -e PYTHONPATH=/app \
                        agentic-rag-backend-test:${BUILD_NUMBER} \
                        pytest backend/tests -q
                '''
            }
        }

        stage('Build Images') {
            steps {
                sh '''
                    set -e

                    echo "Building backend image..."
                    docker build \
                        -f backend/Dockerfile \
                        -t ${BACKEND_IMAGE}:${BUILD_NUMBER} \
                        -t ${BACKEND_IMAGE}:latest \
                        .

                    echo "Building frontend image..."
                    docker build \
                        -f frontend/Dockerfile \
                        -t ${FRONTEND_IMAGE}:${BUILD_NUMBER} \
                        -t ${FRONTEND_IMAGE}:latest \
                        frontend
                '''
            }
        }

        stage('Push Images') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKER_USERNAME',
                        passwordVariable: 'DOCKER_PASSWORD'
                    )
                ]) {
                    sh '''
                        set -e

                        echo "$DOCKER_PASSWORD" | docker login \
                            -u "$DOCKER_USERNAME" \
                            --password-stdin

                        echo "Pushing backend..."
                        docker push ${BACKEND_IMAGE}:${BUILD_NUMBER}
                        docker push ${BACKEND_IMAGE}:latest

                        echo "Pushing frontend..."
                        docker push ${FRONTEND_IMAGE}:${BUILD_NUMBER}
                        docker push ${FRONTEND_IMAGE}:latest

                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    set -e

                    echo "Applying Kubernetes manifests..."

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        apply -f k8s/namespace.yaml

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        apply \
                        -f k8s/configmap.yaml \
                        -f k8s/secret.yaml \
                        -f k8s/persistent-volume.yaml \
                        -f k8s/persistent-volume-claim.yaml \
                        -f k8s/backend-service.yaml \
                        -f k8s/frontend-service.yaml \
                        -f k8s/backend-deployment.yaml \
                        -f k8s/frontend-deployment.yaml \
                        -f k8s/ingress.yaml

                    echo "Updating backend image..."

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        -n ${K8S_NAMESPACE} \
                        set image deployment/backend \
                        backend=${BACKEND_IMAGE}:${BUILD_NUMBER}

                    echo "Updating frontend image..."

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        -n ${K8S_NAMESPACE} \
                        set image deployment/frontend \
                        frontend=${FRONTEND_IMAGE}:${BUILD_NUMBER}

                    echo "Waiting for backend rollout..."

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        -n ${K8S_NAMESPACE} \
                        rollout status deployment/backend \
                        --timeout=180s

                    echo "Waiting for frontend rollout..."

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        -n ${K8S_NAMESPACE} \
                        rollout status deployment/frontend \
                        --timeout=180s
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    set -e

                    echo "Kubernetes pods:"

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        -n ${K8S_NAMESPACE} \
                        get pods

                    echo ""
                    echo "Kubernetes services:"

                    ${KUBECTL} \
                        --kubeconfig=${KUBECONFIG} \
                        --insecure-skip-tls-verify=true \
                        -n ${K8S_NAMESPACE} \
                        get services

                    echo ""
                    echo "Deployment completed successfully."
                '''
            }
        }
    }

    post {
        success {
            echo 'CI/CD pipeline completed successfully!'
        }

        failure {
            echo 'CI/CD pipeline failed. Check the stage logs above.'
        }
    }
}