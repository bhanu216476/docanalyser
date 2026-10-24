package com.docanalyser;

import com.docanalyser.entity.Role;
import com.docanalyser.entity.User;
import com.docanalyser.repository.UserRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.security.crypto.password.PasswordEncoder;

@SpringBootApplication
public class DocAnalyserApplication {
    public static void main(String[] args) {
        SpringApplication.run(DocAnalyserApplication.class, args);
    }

    @Bean
    public CommandLineRunner initAdminUser(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        return args -> {
            String adminEmail = "admin@docanalyser.com";
            userRepository.findByEmail(adminEmail).ifPresentOrElse(
                user -> {
                    if (user.getRole() != Role.ADMIN) {
                        user.setRole(Role.ADMIN);
                        userRepository.save(user);
                        System.out.println(">>> Promoted existing user to ADMIN: " + adminEmail);
                    }
                },
                () -> {
                    User admin = new User(
                        "System Administrator",
                        adminEmail,
                        passwordEncoder.encode("Admin@123456"),
                        Role.ADMIN
                    );
                    admin.setProfileType("Admin");
                    userRepository.save(admin);
                    System.out.println(">>> Initialized default admin user: " + adminEmail);
                }
            );
        };
    }
}
