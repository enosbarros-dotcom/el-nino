targetScope = 'resourceGroup'

@description('Prefixo dos nomes dos recursos')
param prefix string = 'elnino'

@description('Regiao permitida pela politica da assinatura (Azure for Students)')
@allowed([
  'eastus'
  'canadacentral'
  'chilecentral'
  'mexicocentral'
  'brazilsouth'
])
param location string = 'brazilsouth'

@description('Imagem do agente, publicada em registry publico')
param image string = 'ghcr.io/enosbarros-dotcom/el-nino-agent:latest'

@description('vCPU por replica (0.5 = opcao mais barata)')
param cpu string = '0.5'

@description('Memoria por replica (precisa casar com a vCPU)')
param memory string = '1Gi'

@description('Nome do Storage Account do relatorio (3-24 chars, minusculas, globalmente unico)')
param storageName string = 'elninosite561926'

var logsName  = '${prefix}-logs'
var envName   = '${prefix}-env'
var agentName = '${prefix}-agent'

// ---------------------------------------------------------- Logs (30d)
// Retencao minima aceita para conter custo de ingestao.
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logsName
  location: location
  properties: {
    retentionInDays: 30
    sku: { name: 'PerGB2018' }
  }
}

// ------------------------------------------------ Container Apps Env
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// --------------------------------------------- Agente (Streamlit)
resource agent 'Microsoft.App/containerApps@2024-03-01' = {
  name: agentName
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8501
        transport: 'auto'                       // HTTP + WebSocket
        allowInsecure: false                    // forca HTTPS
      }
    }
    template: {
      scale: {
        minReplicas: 0                          // escala para zero => custo ~US$ 0
        maxReplicas: 1                          // replica unica: sessao Streamlit consistente
        rules: [
          {
            name: 'http-concorrencia'
            http: { metadata: { concurrentRequests: '25' } }
          }
        ]
      }
      containers: [
        {
          name: 'agent'
          image: image
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: [
            { name: 'PORT', value: '8501' }
          ]
          // O Streamlit expoe /_stcore/health - evita receber trafego antes de estar pronto
          probes: [
            {
              type: 'startup'
              httpGet: { path: '/_stcore/health', port: 8501 }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 30
            }
            {
              type: 'liveness'
              httpGet: { path: '/_stcore/health', port: 8501 }
              initialDelaySeconds: 15
              periodSeconds: 20
              failureThreshold: 3
            }
          ]
        }
      ]
    }
  }
}

// ------------------------------------ Storage Account (relatorio)
// Static Web Apps nao existe em nenhuma das regioes permitidas pela politica
// da assinatura, entao o relatorio vai para um static website do Blob Storage.
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }              // camada mais barata
  properties: {
    allowBlobPublicAccess: true              // necessario para servir o site estatico
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    accessTier: 'Hot'
  }
}

// O static website e habilitado por CLI (az storage account blob-service-properties
// update --enable-static-website), pois o nome das sub-propriedades varia entre
// api-versions e o provedor rejeita a forma enviada pelo Bicep.

output agentFqdn string = agent.properties.configuration.ingress.fqdn
output siteUrl string = storage.properties.primaryEndpoints.web
output storageAccountName string = storage.name
output storageAccountId string = storage.id
output logAnalyticsId string = logs.id
