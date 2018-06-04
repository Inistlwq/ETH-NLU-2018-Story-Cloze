from utils import Dataloader
from scripts import DefaultScript
import numpy as np
from torch.autograd import Variable
import torch
import time
from utils.Trainer import Seq2SeqTrainer


class Script(DefaultScript):
    slug = 'concept_fb'

    def train(self):
        # self.GLOVE_PATH = '/home/benamira/Bureau/InferSent/dataset/GloVe/glove.840B.300d.txt'
        # self.model = torch.load('/home/benamira/Bureau/InferSent/encoder/infersent.allnli.pickle')
        # self.model.set_glove_path(self.GLOVE_PATH)
        # self.model.build_vocab_k_words(K=100000)
        output_fn = OutputFN(self.config.GLOVE_PATH, self.config.model_path)
        train_set = Dataloader(self.config, 'data/train_stories.csv')
        test_set = Dataloader(self.config, 'data/test_stories.csv', testing_data=True)
        train_set.set_special_tokens(["<unk>"])
        test_set.set_special_tokens(["<unk>"])
        train_set.load_dataset('data/train.bin')
        train_set.load_vocab('./data/default.voc', self.config.vocab_size)
        test_set.load_dataset('data/test.bin')
        test_set.load_vocab('./data/default.voc', self.config.vocab_size)
        test_set.set_output_fn(output_fn.output_fn_test)
        train_set.set_output_fn(output_fn)
        generator_training = train_set.get_batch(self.config.batch_size, self.config.n_epochs)
        generator_dev = test_set.get_batch(self.config.batch_size, self.config.n_epochs)
        epoch = 0
        plot_losses_train = []
        plot_losses_train_adv = []
        plot_losses_train_cross = []
        plot_losses_train_auto = []
        plot_accurracies_avg = []
        plot_accurracies_avg_val = []
        start = time.time()
        Seq2SEq_main_model = Seq2SeqTrainer(self.config.hidden_size, self.config.embedding_size,
                                            self.config.n_layers, self.config.batch_size,
                                            self.config.attention_bolean, dropout=0.5,
                                            learning_rate=0.0003,
                                            plot_every=20, print_every=100, evaluate_every=1000, max_length=100,
                                            learning_rate_discriminator=0.0005)
        plot_loss_total = 0
        plot_discriminator_loss_total = 0
        plot_loss_total_auto = 0
        plot_loss_total_cross = 0
        compteur_val = 0
        while epoch < self.config.n_epochs:
            print("Epoch:", epoch)
            epoch += 1
            for phase in ['train', 'test']:
                print(phase)
                if phase == 'train':
                    for num, batch in enumerate(generator_training):
                        print('NUM BATCH')
                        print(num)
                        main_loss_total, loss_auto_debut, loss_auto_fin, loss_cross_debut, loss_cross_fin, discriminator_loss_total = Seq2SEq_main_model.train_all(
                            batch)
                        plot_loss_total += main_loss_total
                        plot_discriminator_loss_total += discriminator_loss_total
                        plot_loss_total_auto += loss_auto_debut + loss_auto_fin
                        plot_loss_total_cross += loss_cross_debut + loss_cross_fin
                        if num % self.config.plot_every == self.config.plot_every - 1:
                            plot_loss_avg = plot_loss_total / self.config.plot_every
                            plot_loss_adv_avg = plot_discriminator_loss_total / self.config.plot_every
                            plot_loss_auto_avg = plot_loss_total_auto / self.config.plot_every
                            plot_loss_cross_avg = plot_loss_total_cross / self.config.plot_every
                            plot_losses_train.append(plot_loss_avg)
                            plot_losses_train_adv.append(plot_loss_adv_avg)
                            plot_losses_train_auto.append(plot_loss_auto_avg)
                            plot_losses_train_cross.append(plot_loss_cross_avg)
                            np.save('main_loss', np.array(plot_losses_train))
                            np.save('adv_loss', np.array(plot_losses_train_adv))
                            np.save('auto_loss', np.array(plot_losses_train_auto))
                            np.save('cross_loss', np.array(plot_losses_train_cross))
                            print_summary = '%s (%d %d%%) %.4f %.4f %.4f %.4f' % (
                                Seq2SEq_main_model.time_since(start, (num + 1) / (90000 / 32)), (num + 1),
                                (num + 1) / (90000 / 32) * 100,
                                plot_loss_avg, plot_loss_adv_avg, plot_loss_auto_avg, plot_loss_cross_avg)
                            print(print_summary)
                            plot_loss_total = 0
                            plot_discriminator_loss_total = 0
                            plot_loss_total_auto = 0
                            plot_loss_total_cross = 0
                            compteur_val += 1
                        try:
                            if compteur_val == 3:
                                compteur_val = 0
                                correct = 0
                                total = 0
                                for num, batch in enumerate(generator_dev):
                                    if num < 21:
                                        all_histoire_debut_embedding = Variable(torch.LongTensor(batch[0])).transpose(0,
                                                                                                                      1).cuda()
                                        all_histoire_fin_embedding1 = Variable(torch.LongTensor(batch[1])).transpose(0,
                                                                                                                     1).cuda()
                                        all_histoire_fin_embedding2 = Variable(torch.LongTensor(batch[2])).transpose(0,
                                                                                                                     1).cuda()
                                        labels = Variable(torch.LongTensor(batch[3])).cuda()
                                        end = Seq2SEq_main_model.evaluate(Seq2SEq_main_model.encoder_source,
                                                                          Seq2SEq_main_model.decoder_target,
                                                                          all_histoire_debut_embedding,
                                                                          Seq2SEq_main_model.input_length_debut)
                                        debut1 = Seq2SEq_main_model.evaluate(Seq2SEq_main_model.encoder_source,
                                                                             Seq2SEq_main_model.decoder_target,
                                                                             all_histoire_fin_embedding1,
                                                                             Seq2SEq_main_model.input_length_fin)
                                        debut2 = Seq2SEq_main_model.evaluate(Seq2SEq_main_model.encoder_source,
                                                                             Seq2SEq_main_model.decoder_target,
                                                                             all_histoire_fin_embedding2,
                                                                             Seq2SEq_main_model.input_length_fin)
                                        preds = self.get_predict(end, debut1, debut2,
                                                                 all_histoire_debut_embedding.transpose(0, 1),
                                                                 all_histoire_fin_embedding1.transpose(0, 1),
                                                                 all_histoire_fin_embedding2.transpose(0, 1))
                                        correct += (preds == labels).sum().item()
                                        total += self.config.batch_size
                                        print(num)
                                        print(correct / total)
                                        if num % self.config.plot_every_test == self.config.plot_every_test - 1:
                                            plot_acc_avg = correct / total
                                            plot_accurracies_avg_val.append(plot_acc_avg)
                                            np.save('accuracy_val', np.array(plot_accurracies_avg_val))
                                            correct = 0
                                            total = 0
                                    else:
                                        print('done validation')
                                        break
                        except Exception as e:
                            print(e)
                            pass

                else:
                    correct = 0
                    total = 0
                    for num, batch in enumerate(generator_dev):
                        all_histoire_debut_embedding = Variable(torch.LongTensor(batch[0])).transpose(0, 1).cuda()
                        all_histoire_fin_embedding1 = Variable(torch.LongTensor(batch[1])).transpose(0, 1).cuda()
                        all_histoire_fin_embedding2 = Variable(torch.LongTensor(batch[2])).transpose(0, 1).cuda()
                        labels = Variable(torch.LongTensor(batch[3])).cuda()
                        end = Seq2SEq_main_model.evaluate(Seq2SEq_main_model.encoder_source,
                                                          Seq2SEq_main_model.decoder_target,
                                                          all_histoire_debut_embedding,
                                                          Seq2SEq_main_model.input_length_debut)
                        debut1 = Seq2SEq_main_model.evaluate(Seq2SEq_main_model.encoder_source,
                                                             Seq2SEq_main_model.decoder_target,
                                                             all_histoire_fin_embedding1,
                                                             Seq2SEq_main_model.input_length_fin)
                        debut2 = Seq2SEq_main_model.evaluate(Seq2SEq_main_model.encoder_source,
                                                             Seq2SEq_main_model.decoder_target,
                                                             all_histoire_fin_embedding2,
                                                             Seq2SEq_main_model.input_length_fin)
                        preds = self.get_predict(end, debut1, debut2, all_histoire_debut_embedding.transpose(0, 1),
                                                 all_histoire_fin_embedding1.transpose(0, 1),
                                                 all_histoire_fin_embedding2.transpose(0, 1))
                        correct += (preds == labels).sum().item()
                        total += self.config.batch_size
                        print(correct / total)
                        if num % self.config.plot_every_test == self.config.plot_every_test - 1:
                            plot_acc_avg = correct / total
                            plot_accurracies_avg.append(plot_acc_avg)
                            np.save('accuracy_test', np.array(plot_accurracies_avg))
                            correct = 0
                            total = 0
                torch.save(Seq2SEq_main_model.encoder_source.state_dict(), 'encoder_source_epoch' + str(epoch) + '.pth')
                torch.save(Seq2SEq_main_model.encoder_target.state_dict(), 'encoder_target_epoch' + str(epoch) + '.pth')
                torch.save(Seq2SEq_main_model.decoder_source.state_dict(), 'decoder_source_epoch' + str(epoch) + '.pth')
                torch.save(Seq2SEq_main_model.decoder_target.state_dict(), 'decoder_target_epoch' + str(epoch) + '.pth')

    def get_predict(self, end, debut1, debut2, all_histoire_debut_embedding, all_histoire_fin_embedding1,
                    all_histoire_fin_embedding2):
        # Todo : predict selon end, selon debur, selon les 2 (dernier fait ici)
        """
        :param end:
        :param debut1:
        :param debut2:
        :param all_histoire_debut_embedding:
        :param all_histoire_fin_embedding1:
        :param all_histoire_fin_embedding2:
        :return:
        """
        semblable_fin1 = torch.cos(end.float() - all_histoire_fin_embedding1.float())
        semblable_fin2 = torch.cos(end.float() - all_histoire_fin_embedding2.float())
        semblable_debut1 = torch.cos(debut1.float() - all_histoire_debut_embedding.float())
        semblable_debut2 = torch.cos(debut2.float() - all_histoire_debut_embedding.float())
        sf1 = semblable_fin1.sum(2) / self.config.embedding_size
        sf1 = sf1.sum(1) / 1
        sf2 = semblable_fin2.sum(2) / self.config.embedding_size
        sf2 = sf2.sum(1) / 1
        sd1 = semblable_debut1.sum(2) / self.config.embedding_size
        sd1 = sd1.sum(1) / 4
        sd2 = semblable_debut2.sum(2) / self.config.embedding_size
        sd2 = sd2.sum(1) / 4
        p1 = (sf1 + sd1) / 2
        p2 = (sf2 + sd2) / 2
        p = torch.stack((p1, p2))
        (_, pred) = torch.max(p, 0)
        return (pred)


class OutputFN:
    def __init__(self, GLOVE_PATH, model_path):
        self.GLOVE_PATH = GLOVE_PATH
        self.model = torch.load(model_path)
        self.model.set_glove_path(self.GLOVE_PATH)
        self.model.build_vocab_k_words(K=100000)

    def __call__(self, data):
        batch = np.array(data.batch)
        all_histoire_debut_embedding = []
        all_histoire_fin_embedding = []
        all_histoire_noise_debut = []
        all_histoire_noise_fin = []
        all_noise_debut = []
        all_noise_fin = []
        for b in batch:
            histoire_debut = np.array([
                b[0],
                b[1],
                b[2],
                b[3]])
            histoire_noise_debut = self.add_noise(histoire_debut)
            histoire_embedding_debut = self.infersent(histoire_debut)
            histoire_embedding_noise_debut = self.infersent(histoire_noise_debut)
            noise_debut = histoire_embedding_noise_debut - histoire_embedding_debut
            histoire_fin = np.array([
                b[4]])
            histoire_noise_fin = self.add_noise(histoire_fin)
            histoire_embedding_fin = self.infersent(histoire_fin)
            histoire_embedding_noise_fin = self.infersent(histoire_noise_fin)
            noise_fin = histoire_embedding_noise_fin - histoire_embedding_fin
            all_histoire_debut_embedding.append(histoire_embedding_debut)
            all_histoire_fin_embedding.append(histoire_embedding_fin)
            all_histoire_noise_debut.append(histoire_embedding_noise_debut)
            all_histoire_noise_fin.append(histoire_embedding_noise_fin)
            all_noise_debut.append(noise_debut)
            all_noise_fin.append(noise_fin)
        return [np.array(all_histoire_debut_embedding), np.array(all_histoire_fin_embedding),
                np.array(all_histoire_noise_debut), np.array(all_histoire_noise_fin),
                np.array(all_noise_debut), np.array(all_noise_fin)]

    def infersent(self, story):
        """
        :param story:
        :return:
        """
        sentences = []
        for num, sto in enumerate(story):
            sto = ' '.join(sto)
            sentences.append(sto)
            embeddings = self.model.encode(sentences, tokenize=True, verbose=True)
        return (embeddings)

    def output_fn_test(self, data):
        """
        :param data:
        :return:
        """
        batch = np.array(data.batch)
        all_histoire_debut_embedding = []
        all_histoire_fin_embedding1 = []
        all_histoire_fin_embedding2 = []
        label = []
        for b in batch:
            histoire_debut = np.array([
                b[0],
                b[1],
                b[2],
                b[3]])
            histoire_embedding_debut = self.infersent(histoire_debut)
            all_histoire_debut_embedding.append(histoire_embedding_debut)
            histoire_fin1 = np.array([
                b[4]])
            histoire_fin2 = np.array([
                b[5]])
            histoire_embedding_fin1 = self.infersent(histoire_fin1)
            all_histoire_fin_embedding1.append(histoire_embedding_fin1)
            histoire_embedding_fin2 = self.infersent(histoire_fin2)
            all_histoire_fin_embedding2.append(histoire_embedding_fin2)
            label.append(2 - int(b[6][0]))
        return [np.array(all_histoire_debut_embedding), np.array(all_histoire_fin_embedding1),
                np.array(all_histoire_fin_embedding2), np.array(label)]

    def add_noise(self, variable, drop_probability: float = 0.1, shuffle_max_distance: int = 3):
        """
        :param variable:np array that : [[sentence1][sentence2]]
        :param drop_probability: we drop every word in the input sentence with a probability
        :param shuffle_max_distance: we slightly shuffle the input sentence
        :return:
        """

        def perm(i):
            return i[0] + (shuffle_max_distance + 1) * np.random.random()

        liste = []
        for b in range(variable.shape[0]):
            sequence = variable[b]
            if (type(sequence) != list):
                sequence = sequence.tolist()
            sequence, reminder = sequence[:-1], sequence[-1:]
            if len(sequence) != 0:
                compteur = 0
                for num, val in enumerate(np.random.random_sample(len(sequence))):
                    if val < drop_probability:
                        sequence.pop(num - compteur)
                        compteur = compteur + 1
                sequence = [x for _, x in sorted(enumerate(sequence), key=perm)]
            sequence = np.concatenate((sequence, reminder), axis=0)
            liste.append(sequence)
        new_variable = np.array(liste)
        return new_variable