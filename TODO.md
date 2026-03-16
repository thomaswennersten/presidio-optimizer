# Presidio Optimizer - TODO

## Fas 1: Projektsetup & backend-grund
- [x] Skapa katalogstruktur + TODO.md
- [x] Kopiera swedish_recognizers.py och document_processor.py
- [x] Skapa config_manager.py - datamodell + serialisering + versionshantering
- [x] Anpassa presidio_service.py - dynamisk konfiguration via analyze_with_config()
- [x] Skapa custom_recognizer_factory.py - bygg recognizers från config-dicts

## Fas 2: LLM-integration
- [x] Skapa feedback_processor.py - normalisera + aggregera feedback
- [x] Skapa llm_optimizer.py - systemprompt + Claude API-anrop + JSON-parsning

## Fas 3: FastAPI-applikation
- [x] Skapa main.py med alla endpoints + sessionshantering

## Fas 4: Docker
- [x] Skapa requirements.txt
- [x] Skapa Dockerfile
- [x] Skapa docker-compose.yml
- [x] Skapa nginx.conf
- [x] Skapa .env
- [x] Bygga + testa backend

## Fas 5: Frontend
- [x] index.html - sidstruktur
- [x] css/styles.css - entitetsfärger, split-panel, annotationsstilar
- [x] js/api-client.js - API-kommunikationslager
- [x] js/file-upload.js - drag & drop
- [x] js/text-annotator.js - interaktiv textmarkering
- [x] js/config-panel.js - konfigurationsvisning
- [x] js/iteration-history.js - tidslinje + jämförelse
- [x] js/app.js - huvudkontroller

## Fas 6: Nginx & extern åtkomst
- [x] Lägg till location-block i nginx-config
- [x] Starta om nginx + verifiera

## Fas 7: End-to-end-testning
- [x] Testa hela flödet (session -> upload -> analyze -> resultat)

## Fas 8: Namngivna persistenta sessioner
- [x] Skapa session_store.py - filbaserad sessionslagring
- [x] Uppdatera config_manager.py - sökvägsändring (configs underkatlog)
- [x] Uppdatera docker-compose.yml - CONFIG_DIR=/app/db/sessions
- [x] Uppdatera main.py - nya endpoints + SessionStore istället för in-memory
- [x] Uppdatera api-client.js - nya API-metoder (listSessions, downloadFile, etc.)
- [x] Skapa session-manager.js - frontend-komponent för sessionshantering
- [x] Uppdatera index.html - session-manager-sektion + sessionsindikator
- [x] Uppdatera app.js - sessionsflöde + tillbaka-knapp
- [x] Uppdatera styles.css - session-manager-stilar
- [x] Verifiera: starta om container + testa hela flödet
