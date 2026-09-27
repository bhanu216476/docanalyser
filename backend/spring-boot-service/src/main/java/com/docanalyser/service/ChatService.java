package com.docanalyser.service;

import com.docanalyser.entity.ChatMessage;
import com.docanalyser.entity.ChatRole;
import com.docanalyser.entity.ChatSession;
import com.docanalyser.redis.SessionState;
import com.docanalyser.redis.SessionStateService;
import com.docanalyser.repository.ChatMessageRepository;
import com.docanalyser.repository.ChatSessionRepository;
import com.docanalyser.security.services.UserDetailsImpl;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class ChatService {

    private final ChatSessionRepository sessionRepository;
    private final ChatMessageRepository messageRepository;
    private final RagServiceClient ragServiceClient;
    private final SessionStateService sessionStateService;

    @org.springframework.beans.factory.annotation.Autowired
    public ChatService(ChatSessionRepository sessionRepository,
                       ChatMessageRepository messageRepository,
                       RagServiceClient ragServiceClient,
                       SessionStateService sessionStateService) {
        this.sessionRepository = sessionRepository;
        this.messageRepository = messageRepository;
        this.ragServiceClient = ragServiceClient;
        this.sessionStateService = sessionStateService;
    }

    public ChatService(ChatSessionRepository sessionRepository,
                       ChatMessageRepository messageRepository,
                       RagServiceClient ragServiceClient) {
        this(sessionRepository, messageRepository, ragServiceClient, null);
    }

    public ChatSession createSession(String title, UserDetailsImpl userDetails) {
        ChatSession session = new ChatSession(userDetails.getId(), title);
        ChatSession saved = sessionRepository.save(session);

        if (sessionStateService != null) {
            sessionStateService.touchSession(saved.getId(), userDetails.getId());
        }

        return saved;
    }

    public List<ChatSession> getUserSessions(UserDetailsImpl userDetails) {
        return sessionRepository.findByUserIdOrderByCreatedAtDesc(userDetails.getId());
    }

    public ChatSession getSession(UUID sessionId, UserDetailsImpl userDetails) {
        ChatSession session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Session not found"));
        if (!session.getUserId().equals(userDetails.getId())) {
            throw new AccessDeniedException("Access denied");
        }

        if (sessionStateService != null) {
            sessionStateService.touchSession(sessionId, userDetails.getId());
        }

        return session;
    }

    public void deleteSession(UUID sessionId, UserDetailsImpl userDetails) {
        ChatSession session = getSession(sessionId, userDetails);
        if (sessionStateService != null) {
            sessionStateService.deleteSessionState(sessionId);
        }
        sessionRepository.delete(session);
    }

    public ChatMessage sendMessage(UUID sessionId, String content, UserDetailsImpl userDetails) {
        ChatSession session = getSession(sessionId, userDetails);

        // Save user message
        ChatMessage userMessage = new ChatMessage(session.getId(), ChatRole.USER, content);
        messageRepository.save(userMessage);

        // Call RAG python service and extract the answer
        String assistantReply;
        try {
            Map<String, Object> ragResponse = ragServiceClient.queryRagService(content);
            assistantReply = (String) ragResponse.getOrDefault("answer", "No answer provided");
        } catch (Exception e) {
            assistantReply = "Sorry, I am currently unable to process your request. " + e.getMessage();
        }

        // Save assistant message
        ChatMessage assistantMessage = new ChatMessage(session.getId(), ChatRole.ASSISTANT, assistantReply);
        ChatMessage saved = messageRepository.save(assistantMessage);

        if (sessionStateService != null) {
            sessionStateService.touchSession(sessionId, userDetails.getId());
        }

        return saved;
    }

    public List<ChatMessage> getMessages(UUID sessionId, UserDetailsImpl userDetails) {
        getSession(sessionId, userDetails); // Validate ownership & touch session
        return messageRepository.findBySessionIdOrderByCreatedAtAsc(sessionId);
    }

    public Optional<SessionState> getActiveSessionState(UUID sessionId, UserDetailsImpl userDetails) {
        getSession(sessionId, userDetails); // Validate ownership
        if (sessionStateService != null) {
            return sessionStateService.getSessionState(sessionId);
        }
        return Optional.empty();
    }
}
