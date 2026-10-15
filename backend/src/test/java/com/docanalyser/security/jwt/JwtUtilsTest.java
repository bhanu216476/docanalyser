package com.docanalyser.security.jwt;

import com.docanalyser.security.services.UserDetailsImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.TestPropertySource;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@TestPropertySource(properties = {
        "app.jwt.secret=test-secret-key-for-unit-tests-only-32chars",
        "app.jwt.expiration-ms=3600000"
})
class JwtUtilsTest {

    @Autowired
    private JwtUtils jwtUtils;

    private Authentication authentication;
    private UserDetailsImpl userDetails;

    @BeforeEach
    void setUp() {
        List<GrantedAuthority> authorities = List.of(new SimpleGrantedAuthority("ROLE_USER"));
        userDetails = new UserDetailsImpl(
                UUID.randomUUID(),
                "Test User",
                "test@example.com",
                "hashed",
                authorities,
                true);
        authentication = new UsernamePasswordAuthenticationToken(userDetails, null, userDetails.getAuthorities());
    }

    @Test
    void generateJwtToken_validAuthentication_returnsToken() {
        String token = jwtUtils.generateJwtToken(authentication);
        assertThat(token).isNotBlank();
    }

    @Test
    void validateJwtToken_validToken_returnsTrue() {
        String token = jwtUtils.generateJwtToken(authentication);
        assertThat(jwtUtils.validateJwtToken(token)).isTrue();
    }

    @Test
    void validateJwtToken_invalidToken_returnsFalse() {
        assertThat(jwtUtils.validateJwtToken("invalid.token.value")).isFalse();
    }

    @Test
    void validateJwtToken_emptyString_returnsFalse() {
        assertThat(jwtUtils.validateJwtToken("")).isFalse();
    }

    @Test
    void getUsernameFromJwtToken_validToken_returnsEmail() {
        String token = jwtUtils.generateJwtToken(authentication);
        String username = jwtUtils.getUsernameFromJwtToken(token);
        assertThat(username).isEqualTo("test@example.com");
    }
}
